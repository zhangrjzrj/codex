#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import select
import socket
import time
from pathlib import Path


IAC = 255
DONT = 254
DO = 253
WONT = 252
WILL = 251
SB = 250
SE = 240

TELNET_PORT_RE = re.compile(r"Telnet Server Binded on Port\s+[0-9\.:]+:(\d+)")


def parse_auto_json(output: str) -> dict:
    payload = None
    for line in output.splitlines():
        if "AUTO_JSON::" not in line:
            continue
        payload = line.split("AUTO_JSON::", 1)[1].strip()
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {}


def discover_ports_from_logs(log_dir: Path, limit: int = 6) -> list[int]:
    if not log_dir.exists():
        return []

    logs = sorted(log_dir.glob("ClientLog-*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[int] = []
    for log_path in logs[:limit]:
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in TELNET_PORT_RE.finditer(text):
            port = int(match.group(1))
            if port not in out:
                out.append(port)
    return out


class TelnetDriver:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9113,
        connect_timeout: float = 3.0,
        log_dir: Path | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.log_dir = log_dir
        self._sock: socket.socket | None = None
        self._rx_pending = b""

    def connect(self) -> int:
        candidates = [self.port]
        if self.log_dir:
            for p in discover_ports_from_logs(self.log_dir):
                if p not in candidates:
                    candidates.append(p)

        last_err: Exception | None = None
        for candidate in candidates:
            try:
                sock = socket.create_connection((self.host, candidate), timeout=self.connect_timeout)
                sock.setblocking(False)
                self._sock = sock
                self.port = candidate
                return candidate
            except Exception as exc:
                last_err = exc

        msg = f"failed to connect telnet host={self.host} candidates={candidates}"
        if last_err:
            raise ConnectionError(f"{msg}, last_error={last_err}") from last_err
        raise ConnectionError(msg)

    def close(self) -> None:
        if self._sock is None:
            return
        try:
            self._sock.close()
        finally:
            self._sock = None

    def _send_raw(self, payload: bytes) -> None:
        if self._sock is None:
            raise RuntimeError("telnet not connected")
        self._sock.sendall(payload)

    def _send_telnet_option_response(self, command: int, option: int) -> None:
        if command == DO:
            resp = bytes([IAC, WONT, option])
        elif command == DONT:
            resp = bytes([IAC, WONT, option])
        elif command == WILL:
            resp = bytes([IAC, DONT, option])
        else:
            resp = bytes([IAC, DONT, option])
        self._send_raw(resp)

    def _process_incoming(self, raw: bytes) -> str:
        buf = self._rx_pending + raw
        out = bytearray()
        i = 0
        n = len(buf)

        while i < n:
            b = buf[i]
            if b != IAC:
                out.append(b)
                i += 1
                continue

            if i + 1 >= n:
                break

            cmd = buf[i + 1]
            if cmd == IAC:
                out.append(IAC)
                i += 2
                continue

            if cmd in (DO, DONT, WILL, WONT):
                if i + 2 >= n:
                    break
                option = buf[i + 2]
                self._send_telnet_option_response(cmd, option)
                i += 3
                continue

            if cmd == SB:
                end = buf.find(bytes([IAC, SE]), i + 2)
                if end == -1:
                    break
                i = end + 2
                continue

            i += 2

        self._rx_pending = buf[i:]
        return out.replace(b"\x00", b"").decode("utf-8", errors="ignore")

    def _read_until_contains(self, token: str, timeout: float, accept_auto_json: bool = False) -> str:
        if self._sock is None:
            raise RuntimeError("telnet not connected")

        deadline = time.time() + timeout
        chunks: list[str] = []
        while time.time() < deadline:
            wait = min(0.25, max(0.01, deadline - time.time()))
            rlist, _, _ = select.select([self._sock], [], [], wait)
            if not rlist:
                continue
            data = self._sock.recv(65536)
            if not data:
                break
            text = self._process_incoming(data)
            if text:
                chunks.append(text)
                whole = "".join(chunks)
                if token in whole:
                    return whole

        whole = "".join(chunks)
        if accept_auto_json and parse_auto_json(whole):
            return whole
        raise TimeoutError(f"timed out waiting token={token!r}, output={whole[-1000:]}")

    @staticmethod
    def _escape_iac(data: bytes) -> bytes:
        return data.replace(bytes([IAC]), bytes([IAC, IAC]))

    def send_line(self, command: str) -> None:
        payload = self._escape_iac((command + "\r\n").encode("utf-8"))
        self._send_raw(payload)

    def command(
        self,
        command: str,
        end_marker: str = "AUTO_END",
        timeout: float = 15.0,
        accept_auto_json: bool = False,
    ) -> str:
        self.send_line(command)
        return self._read_until_contains(end_marker, timeout, accept_auto_json=accept_auto_json)

    def wait_for_text(self, text: str, timeout: float = 20.0) -> str:
        return self._read_until_contains(text, timeout)

    def load_script(self, script_path: Path, success_text: str, timeout: float = 25.0) -> str:
        full_path = script_path.resolve().as_posix()
        cmd = (
            "exec(compile(open("
            f"r'{full_path}',"
            "'rb').read(),"
            f"r'{full_path}',"
            "'exec'), globals(), globals())"
        )
        self.send_line(cmd)
        return self._read_until_contains(success_text, timeout)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Minimal telnet probe for Messiah automation.")
    parser.add_argument("--log-dir", type=Path, default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9113)
    parser.add_argument("--probe", default="_auto_loop_operator.ping()")
    args = parser.parse_args()

    driver = TelnetDriver(host=args.host, port=args.port, log_dir=args.log_dir)
    try:
        port = driver.connect()
        print(f"connected to {args.host}:{port}")
        out = driver.command(args.probe, timeout=10.0)
        print(out)
        print(json.dumps(parse_auto_json(out), ensure_ascii=False))
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(_cli())

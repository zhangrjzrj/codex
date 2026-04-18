#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from telnet_driver import TelnetDriver


def now_iso() -> str:
    return datetime.now().isoformat()


def to_ms(sec: float) -> int:
    return int(sec * 1000)


def parse_ports(raw: str) -> list[int]:
    out: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        out.append(int(token))
    return out


def append_log(log_path: Path, text: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fp:
        fp.write(f"[{now_iso()}] {text}\n")


def run_smoke(args) -> tuple[dict, int]:
    started = time.time()
    attempts: list[dict] = []
    status = "connect_fail"
    connected_port = None
    handshake_excerpt = ""
    probe_excerpt = ""
    error = ""

    for port in args.ports:
        t0 = time.time()
        attempt = {
            "port": port,
            "status": "connect_fail",
            "elapsed_ms": None,
            "error": "",
        }
        driver = TelnetDriver(
            host=args.host,
            port=port,
            connect_timeout=args.connect_timeout_sec,
            log_dir=None,
        )
        append_log(args.raw_log_path, f"TRY_CONNECT port={port}")
        try:
            used_port = driver.connect()
            connected_port = used_port
            attempt["status"] = "connected"
            append_log(args.raw_log_path, f"CONNECT_OK port={used_port}")

            # Handshake stage.
            try:
                banner = driver.wait_for_text(args.handshake_token, timeout=args.io_timeout_sec)
                handshake_excerpt = banner[-1200:]
                append_log(args.raw_log_path, "HANDSHAKE_OK")
            except Exception as exc:
                status = "connect_ok_handshake_fail"
                attempt["status"] = status
                attempt["error"] = repr(exc)
                error = repr(exc)
                append_log(args.raw_log_path, f"HANDSHAKE_FAIL err={repr(exc)}")
                break

            # Probe stage.
            try:
                probe_output = driver.command(
                    args.probe_cmd,
                    end_marker=args.probe_end_token,
                    timeout=args.io_timeout_sec,
                )
                probe_excerpt = probe_output[-1200:]
                append_log(args.raw_log_path, f"PROBE_OUTPUT {probe_output[-200:].replace(chr(10), ' ')}")
                if args.probe_expect and args.probe_expect not in probe_output:
                    status = "handshake_ok_probe_fail"
                    attempt["status"] = status
                    attempt["error"] = (
                        f"probe output missing expected token: {args.probe_expect!r}"
                    )
                    error = attempt["error"]
                    append_log(args.raw_log_path, f"PROBE_FAIL err={error}")
                    break
                status = "probe_ok"
                attempt["status"] = status
                append_log(args.raw_log_path, "PROBE_OK")
                break
            except Exception as exc:
                status = "handshake_ok_probe_fail"
                attempt["status"] = status
                attempt["error"] = repr(exc)
                error = repr(exc)
                append_log(args.raw_log_path, f"PROBE_FAIL err={repr(exc)}")
                break
        except Exception as exc:
            attempt["status"] = "connect_fail"
            attempt["error"] = repr(exc)
            append_log(args.raw_log_path, f"CONNECT_FAIL port={port} err={repr(exc)}")
        finally:
            attempt["elapsed_ms"] = to_ms(time.time() - t0)
            attempts.append(attempt)
            driver.close()

    if status == "connect_fail":
        # If we never connected, return the last connect error for convenience.
        for item in reversed(attempts):
            if item.get("error"):
                error = item["error"]
                break

    result = {
        "created_at": now_iso(),
        "host": args.host,
        "ports": args.ports,
        "connect_timeout_sec": args.connect_timeout_sec,
        "io_timeout_sec": args.io_timeout_sec,
        "status": status,
        "connected_port": connected_port,
        "elapsed_ms": to_ms(time.time() - started),
        "probe_cmd": args.probe_cmd,
        "probe_expect": args.probe_expect,
        "error": error,
        "attempts": attempts,
        "handshake_output_excerpt": handshake_excerpt,
        "probe_output_excerpt": probe_excerpt,
    }
    code = 0 if status == "probe_ok" else 1
    return result, code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fast-fail telnet smoke checker for Messiah.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--ports", default="9113,9114,9115")
    parser.add_argument("--connect-timeout-sec", type=float, default=5.0)
    parser.add_argument("--io-timeout-sec", type=float, default=5.0)
    parser.add_argument("--handshake-token", default="Welcome to messiah server")
    parser.add_argument("--probe-cmd", default="1+1")
    parser.add_argument("--probe-end-token", default=">>> ")
    parser.add_argument("--probe-expect", default="2")
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=Path(r"E:/messiah_h74/artifacts/telnet_smoke"),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.ports = parse_ports(args.ports)

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = args.artifacts_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    args.raw_log_path = run_dir / "raw_io.log"

    result, code = run_smoke(args)
    result_path = run_dir / "result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"result_path={result_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

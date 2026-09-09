#!/usr/bin/env python3
from __future__ import annotations

import http.server
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from urllib import request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fallback_router as router


def _handler(mode: str):
    class MockHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length)
            if mode == "primary":
                payload = json.dumps({"error": {"message": "capacity", "code": 429}}).encode("utf-8")
                self.send_response(429)
            else:
                payload = json.dumps({"route": "backup", "echo": body.decode("utf-8")}).encode("utf-8")
                self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return MockHandler


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _serve(port: int, mode: str) -> http.server.ThreadingHTTPServer:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _handler(mode))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> int:
    primary_port = _free_port()
    backup_port = _free_port()
    router_port = _free_port()
    _serve(primary_port, "primary")
    _serve(backup_port, "backup")

    os.environ.update(
        {
            "J_PRIMARY_BASE": f"http://127.0.0.1:{primary_port}/v1",
            "J_PRIMARY_KEY": "primary-key",
            "J_SECONDARY_BASE": f"http://127.0.0.1:{backup_port}/v1",
            "J_SECONDARY_KEY": "backup-key",
            "J_PORT": str(router_port),
        }
    )
    threading.Thread(target=router.main, daemon=True).start()
    time.sleep(1.0)

    req = request.Request(
        f"http://127.0.0.1:{router_port}/v1/responses",
        data=json.dumps({"model": "test", "input": "hello"}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=10) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200, resp.status
        assert resp.headers.get("X-J-Route") == "backup", resp.headers.get("X-J-Route")
        assert payload["route"] == "backup", payload

    print("smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

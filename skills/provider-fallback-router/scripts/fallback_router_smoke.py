#!/usr/bin/env python3
from __future__ import annotations

import http.server
import json
import os
import socket
import threading
import time
from urllib import request

import fallback_router as router


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _handler(state: dict[str, object], route: str):
    class MockHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length)
            state[f"{route}_calls"] = int(state.get(f"{route}_calls", 0)) + 1
            mode = state.get(route, "success")

            if mode == "http_error":
                payload = b'{"error":"capacity"}'
                self.send_response(503)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            if mode == "disconnect_before_body":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                self.close_connection = True
                return

            if mode == "disconnect_after_body":
                payload = b"data: partial\n\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                self.wfile.write(f"{len(payload):X}\r\n".encode("ascii"))
                self.wfile.write(payload + b"\r\n")
                self.wfile.flush()
                self.close_connection = True
                return

            payload = json.dumps(
                {"route": route, "echo": body.decode("utf-8")}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return MockHandler


def _serve(port: int, state: dict[str, object], route: str):
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), _handler(state, route)
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> int:
    primary_port = _free_port()
    backup_port = _free_port()
    router_port = _free_port()
    state: dict[str, object] = {"primary": "success", "backup": "success"}

    primary_server = _serve(primary_port, state, "primary")
    backup_server = _serve(backup_port, state, "backup")
    os.environ.update(
        {
            "J_PRIMARY_BASE": f"http://127.0.0.1:{primary_port}/v1",
            "J_PRIMARY_KEY": "primary-key",
            "J_SECONDARY_BASE": f"http://127.0.0.1:{backup_port}/v1",
            "J_SECONDARY_KEY": "backup-key",
            "J_PORT": str(router_port),
        }
    )
    router_server = router.ThreadingHTTPServer(("127.0.0.1", router_port), router.Handler)
    threading.Thread(target=router_server.serve_forever, daemon=True).start()
    time.sleep(0.1)

    def call() -> tuple[str, bytes]:
        upstream_request = request.Request(
            f"http://127.0.0.1:{router_port}/v1/responses",
            data=b'{"input":"hello"}',
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(upstream_request, timeout=10) as response:
            return str(response.headers.get("X-J-Route")), response.read()

    route, body = call()
    assert route == "primary"
    assert json.loads(body)["route"] == "primary"

    state["primary"] = "http_error"
    route, body = call()
    assert route == "backup"
    assert json.loads(body)["route"] == "backup"

    state["primary"] = "disconnect_before_body"
    route, body = call()
    assert route == "backup"
    assert json.loads(body)["route"] == "backup"

    backup_calls = int(state["backup_calls"])
    state["primary"] = "disconnect_after_body"
    route, body = call()
    assert route == "primary"
    assert body == b"data: partial\n\n"
    assert int(state["backup_calls"]) == backup_calls

    router_server.shutdown()
    primary_server.shutdown()
    backup_server.shutdown()
    print("smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

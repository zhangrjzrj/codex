#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable
from urllib import error, request


@dataclass(frozen=True)
class Upstream:
    name: str
    base_url: str
    api_key: str


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing env: {name}")
    return value


def _upstreams() -> list[Upstream]:
    return [
        Upstream("primary", _env("J_PRIMARY_BASE"), _env("J_PRIMARY_KEY")),
        Upstream("backup", _env("J_SECONDARY_BASE"), _env("J_SECONDARY_KEY")),
    ]


def _join(base: str, path: str) -> str:
    base = base.rstrip("/")
    path = path.lstrip("/")
    if base.endswith("/v1") and path.startswith("v1/"):
        path = path[3:]
    return base + "/" + path


def _copy_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in headers:
        lower = key.lower()
        if lower in {"host", "content-length", "connection", "accept-encoding", "authorization"}:
            continue
        out[key] = value
    return out


def _fallback_status(code: int) -> bool:
    return code in {401, 403, 429} or code >= 500


def _open_upstream(
    upstream: Upstream,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    timeout: int,
) -> request.addinfourl:
    req = request.Request(
        _join(upstream.base_url, path),
        data=body if body else None,
        method=method,
        headers={
            **headers,
            "Authorization": f"Bearer {upstream.api_key}",
            "Accept": headers.get("Accept", "application/json"),
        },
    )
    return request.urlopen(req, timeout=timeout)


def _error_response(exc: error.HTTPError) -> tuple[int, dict[str, str], bytes]:
    return exc.code, dict(exc.headers.items()), exc.read()


class Handler(BaseHTTPRequestHandler):
    server_version = "JFallbackRouter/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def _handle(self) -> None:
        timeout = int(os.environ.get("J_TIMEOUT_SEC", "60"))
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        headers = _copy_headers(self.headers.items())
        last_error: str | None = None

        for index, upstream in enumerate(_upstreams()):
            response = None
            try:
                response = _open_upstream(
                    upstream, self.command, self.path, raw, headers, timeout
                )
                status = response.status
                response_headers = dict(response.headers.items())
            except error.HTTPError as exc:
                status, response_headers, response_body = _error_response(exc)
                if index == 0 and _fallback_status(status):
                    last_error = f"{upstream.name} returned {status}"
                    continue
                self.send_response(status)
                for key, value in response_headers.items():
                    if key.lower() not in {"transfer-encoding", "content-length", "connection", "content-encoding"}:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(response_body)))
                self.send_header("X-J-Route", upstream.name)
                self.end_headers()
                self.wfile.write(response_body)
                return
            except (error.URLError, TimeoutError, OSError) as exc:
                last_error = f"{upstream.name}: {exc}"
                continue

            if index == 0 and _fallback_status(status):
                last_error = f"{upstream.name} returned {status}"
                response.close()
                continue

            self.send_response(status)
            for key, value in response_headers.items():
                if key.lower() not in {"transfer-encoding", "content-length", "connection", "content-encoding"}:
                    self.send_header(key, value)
            self.send_header("X-J-Route", upstream.name)
            self.end_headers()
            while True:
                chunk = response.readline()
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
            response.close()
            return

        body = json.dumps({"error": last_error or "no upstream available"}).encode("utf-8")
        self.send_response(502)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/health", "/"}:
            body = json.dumps({"ok": True, "ts": time.time()}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def do_PUT(self) -> None:  # noqa: N802
        self._handle()

    def do_PATCH(self) -> None:  # noqa: N802
        self._handle()

    def do_DELETE(self) -> None:  # noqa: N802
        self._handle()


def main() -> int:
    host = os.environ.get("J_HOST", "127.0.0.1")
    port = int(os.environ.get("J_PORT", "8787"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"listening on http://{host}:{port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

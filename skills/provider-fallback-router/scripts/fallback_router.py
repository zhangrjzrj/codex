#!/usr/bin/env python3
from __future__ import annotations

import http.client
import json
import os
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable
from urllib import error, request


@dataclass(frozen=True)
class Upstream:
    name: str
    base_url: str
    api_key: str


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing env: {name}")
    return value


def _upstreams() -> tuple[Upstream, Upstream]:
    return (
        Upstream("primary", _required_env("J_PRIMARY_BASE"), _required_env("J_PRIMARY_KEY")),
        Upstream("backup", _required_env("J_SECONDARY_BASE"), _required_env("J_SECONDARY_KEY")),
    )


def _join_url(base_url: str, path: str) -> str:
    base_url = base_url.rstrip("/")
    path = path.lstrip("/")
    if base_url.endswith("/v1") and path.startswith("v1/"):
        path = path[3:]
    return f"{base_url}/{path}"


def _forward_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    excluded = {"host", "content-length", "connection", "accept-encoding", "authorization"}
    return {key: value for key, value in headers if key.lower() not in excluded}


def _fallback_status(status: int) -> bool:
    return status in {401, 403, 429} or status >= 500


def _expects_body(method: str, status: int, headers: dict[str, str]) -> bool:
    return (
        method != "HEAD"
        and not 100 <= status < 200
        and status not in {204, 304}
        and headers.get("Content-Length") != "0"
    )


def _open_upstream(
    upstream: Upstream,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    timeout: int,
):
    upstream_request = request.Request(
        _join_url(upstream.base_url, path),
        data=body if body else None,
        method=method,
        headers={
            **headers,
            "Authorization": f"Bearer {upstream.api_key}",
            "Accept": headers.get("Accept", "application/json"),
        },
    )
    return request.urlopen(upstream_request, timeout=timeout)


class Handler(BaseHTTPRequestHandler):
    server_version = "JFallbackRouter/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send_headers(
        self,
        status: int,
        headers: dict[str, str],
        route: str,
        content_length: int | None = None,
    ) -> None:
        self.send_response(status)
        excluded = {"transfer-encoding", "content-length", "connection", "content-encoding"}
        for key, value in headers.items():
            if key.lower() not in excluded:
                self.send_header(key, value)
        if content_length is not None:
            self.send_header("Content-Length", str(content_length))
        self.send_header("X-J-Route", route)
        self.end_headers()

    def _send_error_response(self, upstream: Upstream, exception: error.HTTPError) -> None:
        body = exception.read()
        self._send_headers(exception.code, dict(exception.headers.items()), upstream.name, len(body))
        self.wfile.write(body)

    def _send_gateway_error(self, message: str) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(502)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle(self) -> None:
        timeout = int(os.environ.get("J_TIMEOUT_SEC", "60"))
        body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        headers = _forward_headers(self.headers.items())
        last_error = "no upstream available"

        for index, upstream in enumerate(_upstreams()):
            try:
                response = _open_upstream(
                    upstream, self.command, self.path, body, headers, timeout
                )
            except error.HTTPError as exception:
                if index == 0 and _fallback_status(exception.code):
                    last_error = f"{upstream.name} returned {exception.code}"
                    continue
                self._send_error_response(upstream, exception)
                return
            except (error.URLError, TimeoutError, OSError) as exception:
                last_error = f"{upstream.name}: {exception}"
                if index == 0:
                    continue
                self._send_gateway_error(last_error)
                return

            status = response.status
            response_headers = dict(response.headers.items())
            try:
                first_chunk = response.readline()
                if not first_chunk and _expects_body(
                    self.command, status, response_headers
                ):
                    raise ConnectionError("upstream closed before response body")
            except (error.URLError, TimeoutError, OSError, http.client.HTTPException) as exception:
                response.close()
                last_error = f"{upstream.name}: {exception}"
                if index == 0:
                    continue
                self._send_gateway_error(last_error)
                return

            self._send_headers(status, response_headers, upstream.name)
            try:
                if first_chunk:
                    self.wfile.write(first_chunk)
                    self.wfile.flush()
                while True:
                    chunk = response.readline()
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (error.URLError, TimeoutError, OSError, http.client.HTTPException):
                self.close_connection = True
            finally:
                response.close()
            return

        self._send_gateway_error(last_error)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/health"}:
            body = json.dumps({"ok": True, "service": "JFallbackRouter"}).encode("utf-8")
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
    ThreadingHTTPServer((host, port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

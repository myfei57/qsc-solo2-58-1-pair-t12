"""Threading HTTP server that speaks the console router."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import BaseServer
from urllib.parse import parse_qs, urlsplit

from portpower.console.errors import error_response
from portpower.console.http import Request, Response
from portpower.console.router import Router

MAX_BODY_BYTES = 4 * 1024 * 1024


class _RequestHandler(BaseHTTPRequestHandler):
    router: Router
    server_version = "PortPowerConsole/1.0"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        self._handle("POST")

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        self._handle("DELETE")

    def _handle(self, method: str) -> None:
        try:
            request = self._build_request(method)
        except ValueError as exc:
            self._write(Response.json(400, {"error": str(exc)}))
            return
        try:
            response = self.router.dispatch(request)
        except Exception as exc:  # pragma: no cover - defensive boundary
            response = error_response(exc)
        self._write(response)

    def _build_request(self, method: str) -> Request:
        parsed = urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        body = self.rfile.read(length) if length > 0 else b""
        query = parse_qs(parsed.query, keep_blank_values=True)
        headers = {name.lower(): value for name, value in self.headers.items()}
        return Request(
            method=method,
            path=parsed.path,
            query=query,
            headers=headers,
            body=body,
        )

    def _write(self, response: Response) -> None:
        self.send_response(response.status)
        if response.payload:
            self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.payload)))
        for name, value in response.headers.items():
            self.send_header(name, value)
        self.end_headers()
        if response.payload:
            self.wfile.write(response.payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def make_http_server(
    router: Router,
    host: str,
    port: int,
    server_class: type[BaseServer] = ThreadingHTTPServer,
):
    handler = type("ConsoleRequestHandler", (_RequestHandler,), {"router": router})
    return server_class((host, port), handler)


class ConsoleServer:
    """Owns the HTTP server and the background serving thread."""

    def __init__(self, router: Router, host: str, port: int) -> None:
        self._httpd = make_http_server(router, host, port)
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._httpd.server_address[:2]
        return str(host), int(port)

    @property
    def url(self) -> str:
        host, port = self.address
        return f"http://{host}:{port}"

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("server already started")
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="console-server",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

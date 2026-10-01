"""Method + path router with a stable route table."""

from __future__ import annotations

from collections.abc import Callable

from portpower.console.http import Request, Response

Handler = Callable[[Request], Response]


class Router:
    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], Handler] = {}
        self._known_paths: dict[str, set[str]] = {}

    def add(self, method: str, path: str, handler: Handler) -> None:
        key = (method.upper(), path)
        if key in self._routes:
            raise ValueError(f"duplicate route {key[0]} {key[1]}")
        self._routes[key] = handler
        self._known_paths.setdefault(path, set()).add(method.upper())

    def get(self, path: str, handler: Handler) -> None:
        self.add("GET", path, handler)

    def post(self, path: str, handler: Handler) -> None:
        self.add("POST", path, handler)

    def delete(self, path: str, handler: Handler) -> None:
        self.add("DELETE", path, handler)

    def dispatch(self, request: Request) -> Response:
        method = request.method.upper()
        handler = self._routes.get((method, request.path))
        if handler is not None:
            return handler(request)
        allowed = self._known_paths.get(request.path)
        if allowed:
            return Response.json(
                405,
                {"error": "method not allowed", "allowed": sorted(allowed)},
            )
        return Response.json(404, {"error": "unknown route", "path": request.path})

    def describe(self) -> list[str]:
        return [f"{method} {path}" for method, path in sorted(self._routes)]

    def __len__(self) -> int:
        return len(self._routes)

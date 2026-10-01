"""Minimal HTTP request and response value objects."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


class BadRequest(ValueError):
    """Raised when a request body cannot be understood."""


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    query: Mapping[str, list[str]]
    headers: Mapping[str, str]
    body: bytes = b""

    def query_one(self, name: str, default: str | None = None) -> str | None:
        values = self.query.get(name)
        if not values:
            return default
        return values[0]

    def json_body(self) -> Any:
        if not self.body:
            return {}
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise BadRequest(f"invalid JSON body: {exc}") from exc

    def json_object(self) -> dict[str, Any]:
        payload = self.json_body()
        if not isinstance(payload, dict):
            raise BadRequest("request body must be a JSON object")
        return payload


@dataclass(frozen=True)
class Response:
    status: int
    payload: bytes
    content_type: str = "application/json; charset=utf-8"
    headers: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def json(cls, status: int, value: Any) -> "Response":
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        return cls(status=status, payload=body)

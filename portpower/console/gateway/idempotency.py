"""Replay cache so retried writes neither re-execute nor consume quota.

A client tags a logical operation with an ``Idempotency-Key`` header.
The first execution stores its successful response; later arrivals of
the same key replay that response verbatim instead of running the
handler again, and they never touch the rate limiter. Records expire
after a TTL and the document is swept on every store.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from portpower.console.http import Response
from portpower.store.kvstore import RecordStore

STORE_KEY = "console.idempotency"
DEFAULT_TTL_SECONDS = 24 * 60 * 60
MAX_KEY_LENGTH = 255


@dataclass(frozen=True)
class StoredResponse:
    status: int
    body: str
    content_type: str
    expires_at: float

    def to_response(self, key: str) -> Response:
        return Response(
            status=self.status,
            payload=self.body.encode("utf-8"),
            content_type=self.content_type,
            headers={"Idempotency-Key": key, "Idempotency-Replayed": "true"},
        )


class IdempotencyCache:
    """Durable map from (client, key) to the response first produced."""

    def __init__(
        self,
        store: RecordStore,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._ttl = ttl_seconds
        self._clock = clock
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    def lock_for(self, client: str, key: str) -> threading.Lock:
        """Serialize concurrent arrivals of the same key."""

        scope = _scope(client, key)
        with self._guard:
            lock = self._locks.get(scope)
            if lock is None:
                lock = threading.Lock()
                self._locks[scope] = lock
            return lock

    def lookup(self, client: str, key: str) -> StoredResponse | None:
        entry = self._read().get(_scope(client, key))
        if not isinstance(entry, dict):
            return None
        try:
            stored = StoredResponse(
                status=int(entry["status"]),
                body=str(entry["body"]),
                content_type=str(
                    entry.get("content_type", "application/json; charset=utf-8")
                ),
                expires_at=float(entry["expires_at"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
        if stored.expires_at <= self._clock():
            return None
        return stored

    def store(self, client: str, key: str, response: Response) -> None:
        record = {
            "status": response.status,
            "body": response.payload.decode("utf-8", errors="replace"),
            "content_type": response.content_type,
            "expires_at": self._clock() + self._ttl,
        }

        def mutate(doc: Any) -> tuple[Any, None]:
            doc = doc if isinstance(doc, dict) else {}
            now = self._clock()
            doc = {
                scope: entry
                for scope, entry in doc.items()
                if _unexpired(entry, now)
            }
            doc[_scope(client, key)] = record
            return doc, None

        self._store.update_json(STORE_KEY, mutate)

    def _read(self) -> dict[str, Any]:
        doc = self._store.get_json(STORE_KEY)
        return doc if isinstance(doc, dict) else {}


def _scope(client: str, key: str) -> str:
    return f"{client}\n{key}"


def _unexpired(entry: Any, now: float) -> bool:
    if not isinstance(entry, dict):
        return False
    try:
        return float(entry.get("expires_at", 0.0)) > now
    except (TypeError, ValueError):
        return False

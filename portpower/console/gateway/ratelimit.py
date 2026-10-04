"""Per-client token bucket that only ever meters write requests.

Read-only methods never touch the limiter. The configuration is durable
so operator changes survive restarts; the buckets themselves are
in-memory and refill continuously.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from portpower.store.kvstore import RecordStore

STORE_KEY = "console.rate-limit"
DEFAULT_CAPACITY = 20.0
DEFAULT_REFILL_PER_SECOND = 5.0


@dataclass(frozen=True)
class RateLimitConfig:
    capacity: float = DEFAULT_CAPACITY
    refill_per_second: float = DEFAULT_REFILL_PER_SECOND
    enabled: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "capacity": self.capacity,
            "refill_per_second": self.refill_per_second,
            "enabled": self.enabled,
        }


class RateLimiter:
    """One token bucket per client identity, shared across write paths."""

    def __init__(
        self,
        store: RecordStore,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._store = store
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: dict[str, tuple[float, float]] = {}

    def config(self) -> RateLimitConfig:
        doc = self._store.get_json(STORE_KEY)
        if not isinstance(doc, dict):
            return RateLimitConfig()
        try:
            return RateLimitConfig(
                capacity=float(doc.get("capacity", DEFAULT_CAPACITY)),
                refill_per_second=float(
                    doc.get("refill_per_second", DEFAULT_REFILL_PER_SECOND)
                ),
                enabled=bool(doc.get("enabled", True)),
            )
        except (TypeError, ValueError):
            return RateLimitConfig()

    def configure(
        self,
        capacity: float | None = None,
        refill_per_second: float | None = None,
        enabled: bool | None = None,
    ) -> RateLimitConfig:
        current = self.config()
        updated = RateLimitConfig(
            capacity=current.capacity if capacity is None else float(capacity),
            refill_per_second=(
                current.refill_per_second
                if refill_per_second is None
                else float(refill_per_second)
            ),
            enabled=current.enabled if enabled is None else bool(enabled),
        )
        if updated.capacity < 1:
            raise ValueError("capacity must be at least 1")
        if updated.refill_per_second <= 0:
            raise ValueError("refill_per_second must be positive")
        self._store.put_json(STORE_KEY, updated.as_dict())
        return updated

    def allow(self, client: str) -> tuple[bool, float]:
        """Take one token; returns (allowed, seconds until the next token)."""

        config = self.config()
        if not config.enabled:
            return True, 0.0
        now = self._clock()
        with self._lock:
            tokens, updated = self._buckets.get(client, (config.capacity, now))
            tokens = min(
                config.capacity,
                tokens + max(0.0, now - updated) * config.refill_per_second,
            )
            if tokens >= 1.0:
                self._buckets[client] = (tokens - 1.0, now)
                return True, 0.0
            self._buckets[client] = (tokens, now)
            return False, (1.0 - tokens) / config.refill_per_second

    def snapshot(self) -> dict[str, Any]:
        config = self.config()
        now = self._clock()
        with self._lock:
            clients = {
                client: round(
                    min(
                        config.capacity,
                        tokens
                        + max(0.0, now - updated) * config.refill_per_second,
                    ),
                    3,
                )
                for client, (tokens, updated) in sorted(self._buckets.items())
            }
        return {"config": config.as_dict(), "clients": clients}

"""Write-rate limiting and idempotent-replay caching.

Only mutating requests are limited; reads never touch the buckets.  Each
client gets a token bucket and the process shares one global bucket, so a
single misbehaving client is throttled without hiding a fleet-wide flood.

A request that carries an ``Idempotency-Key`` is answered from the cache
when the key was seen before: the replay costs no token and the handler
does not run again, so retries of an already-applied write are never
blocked by the limiter.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

Clock = Callable[[], float]


class TokenBucket:
    """Single token bucket refilled at a steady rate."""

    def __init__(self, capacity: float, refill_per_second: float, clock: Clock) -> None:
        if capacity <= 0:
            raise ValueError("bucket capacity must be positive")
        if refill_per_second <= 0:
            raise ValueError("bucket refill rate must be positive")
        self.capacity = float(capacity)
        self.refill = float(refill_per_second)
        self._clock = clock
        self._tokens = float(capacity)
        self._updated = clock()

    def _fill(self, now: float) -> None:
        elapsed = max(0.0, now - self._updated)
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill)
        self._updated = now

    def probe(self) -> float:
        """Seconds until one token is available; 0.0 when available now."""

        self._fill(self._clock())
        if self._tokens >= 1.0:
            return 0.0
        return (1.0 - self._tokens) / self.refill

    def commit(self) -> None:
        """Consume one token; call only after ``probe`` returned 0.0."""

        self._fill(self._clock())
        self._tokens = max(0.0, self._tokens - 1.0)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after: float = 0.0
    scope: str = ""


class RateLimiter:
    """Per-client buckets plus a process-wide bucket for write requests."""

    MAX_CLIENTS = 10000

    def __init__(
        self,
        client_capacity: float,
        client_refill: float,
        global_capacity: float,
        global_refill: float,
        clock: Clock = time.monotonic,
    ) -> None:
        self._clock = clock
        self._client_capacity = client_capacity
        self._client_refill = client_refill
        self._buckets: OrderedDict[str, TokenBucket] = OrderedDict()
        self._global = TokenBucket(global_capacity, global_refill, clock)
        self._lock = threading.Lock()

    def check(self, client: str) -> Decision:
        """Take one token from both buckets, or report when to retry."""

        with self._lock:
            bucket = self._bucket(client)
            client_wait = bucket.probe()
            global_wait = self._global.probe()
            if client_wait <= 0.0 and global_wait <= 0.0:
                bucket.commit()
                self._global.commit()
                return Decision(allowed=True)
            return Decision(
                allowed=False,
                retry_after=max(client_wait, global_wait),
                scope="client" if client_wait >= global_wait else "global",
            )

    def _bucket(self, client: str) -> TokenBucket:
        bucket = self._buckets.get(client)
        if bucket is None:
            if len(self._buckets) >= self.MAX_CLIENTS:
                self._buckets.popitem(last=False)
            bucket = TokenBucket(self._client_capacity, self._client_refill, self._clock)
            self._buckets[client] = bucket
        return bucket


class IdempotencyMismatch(RuntimeError):
    """The same idempotency key arrived with a different request."""


@dataclass(frozen=True)
class CachedResponse:
    status: int
    payload: bytes
    content_type: str


class IdempotencyStore:
    """Remembers responses by idempotency key so replays are free and safe."""

    def __init__(
        self,
        ttl_seconds: float = 86400.0,
        max_entries: int = 10000,
        clock: Clock = time.monotonic,
    ) -> None:
        self._ttl = float(ttl_seconds)
        self._max = max_entries
        self._clock = clock
        self._entries: OrderedDict[tuple[str, str], tuple[float, str, CachedResponse]] = (
            OrderedDict()
        )
        self._lock = threading.Lock()

    def lookup(self, client: str, key: str, fingerprint: str) -> CachedResponse | None:
        with self._lock:
            entry = self._entries.get((client, key))
            if entry is None:
                return None
            stored_at, stored_fingerprint, response = entry
            if self._clock() - stored_at > self._ttl:
                del self._entries[(client, key)]
                return None
            if stored_fingerprint != fingerprint:
                raise IdempotencyMismatch(key)
            return response

    def store(
        self, client: str, key: str, fingerprint: str, response: CachedResponse
    ) -> None:
        with self._lock:
            self._entries[(client, key)] = (self._clock(), fingerprint, response)
            self._entries.move_to_end((client, key))
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)

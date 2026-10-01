"""External breaker state exposed by the status endpoints."""

from __future__ import annotations

from enum import Enum


class BreakerState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    TRIPPED = "tripped"

    @property
    def conducts(self) -> bool:
        return self is BreakerState.CLOSED

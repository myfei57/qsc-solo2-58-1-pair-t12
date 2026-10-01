"""Trip and reset operations for the shore breaker."""

from __future__ import annotations

from portpower.disconn.breaker import Breaker


class BreakerAlreadyClosed(RuntimeError):
    """Raised when resetting a breaker that never opened."""


def trip_breaker(breaker: Breaker) -> None:
    breaker.mark_tripped()


def reset_breaker(breaker: Breaker) -> None:
    if breaker.closed:
        raise BreakerAlreadyClosed(f"breaker {breaker.identifier} is already closed")
    breaker.clear_trip()
    breaker.mark_closed()

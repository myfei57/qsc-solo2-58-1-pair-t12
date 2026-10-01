"""Opening the breaker on demand."""

from __future__ import annotations

from portpower.disconn.breaker import Breaker, BreakerNotClosed


def open_breaker(breaker: Breaker) -> None:
    if not breaker.closed:
        raise BreakerNotClosed(f"breaker {breaker.identifier} is not closed")
    breaker.mark_open()

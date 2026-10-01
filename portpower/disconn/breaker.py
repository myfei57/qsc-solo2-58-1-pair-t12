"""Shore breaker with closed and tripped flags."""

from __future__ import annotations

from portpower.disconn.state import BreakerState


class BreakerNotClosed(RuntimeError):
    """Raised when the breaker is asked to open while it is already open."""


class Breaker:
    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        self._closed = False
        self._tripped = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def tripped(self) -> bool:
        return self._tripped

    @property
    def state(self) -> BreakerState:
        if self._tripped:
            return BreakerState.TRIPPED
        if self._closed:
            return BreakerState.CLOSED
        return BreakerState.OPEN

    def mark_closed(self) -> None:
        self._closed = True

    def mark_open(self) -> None:
        self._closed = False

    def mark_tripped(self) -> None:
        self._tripped = True
        self._closed = False

    def clear_trip(self) -> None:
        self._tripped = False

    def describe(self) -> dict[str, object]:
        return {
            "id": self.identifier,
            "state": self.state.value,
            "closed": self._closed,
            "tripped": self._tripped,
        }

"""Vessel-side breaker arming flag used by the closing interlocks."""

from __future__ import annotations


class BreakerArm:
    def __init__(self) -> None:
        self._armed = False

    @property
    def armed(self) -> bool:
        return self._armed

    def arm(self) -> None:
        self._armed = True

"""Thermal protection that trips the breaker on filtered temperature."""

from __future__ import annotations

from portpower.cable.filter import MovingAverageFilter
from portpower.disconn.breaker import Breaker
from portpower.disconn.open import open_breaker


class Protector:
    def __init__(self, threshold: float, filter_: MovingAverageFilter) -> None:
        if threshold <= 0:
            raise ValueError("protection threshold must be positive")
        self._threshold = threshold
        self._filter = filter_
        self._tripped = False
        self._breaches = 0

    @property
    def threshold(self) -> float:
        return self._threshold

    @property
    def tripped(self) -> bool:
        return self._tripped

    @property
    def breaches(self) -> int:
        return self._breaches

    def reset_filter(self) -> None:
        self._filter.reset()

    def verdict(self, sample: float) -> bool:
        filtered = self._filter.add(sample)
        if filtered > self._threshold:
            self._tripped = True
            self._breaches += 1
            return True
        return False

    def open_and_reset(self, breaker: Breaker) -> None:
        if breaker.closed:
            open_breaker(breaker)
        self.reset_filter()
        self._tripped = False

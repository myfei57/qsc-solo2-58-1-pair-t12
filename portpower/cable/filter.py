"""Fixed-window moving average used to damp temperature spikes."""

from __future__ import annotations

from collections import deque


class MovingAverageFilter:
    def __init__(self, size: int) -> None:
        if size <= 0:
            raise ValueError("filter size must be positive")
        self._size = size
        self._window: deque[float] = deque(maxlen=size)

    def add(self, sample: float) -> float:
        self._window.append(float(sample))
        return self.average

    @property
    def average(self) -> float:
        if not self._window:
            return 0.0
        return sum(self._window) / len(self._window)

    def reset(self) -> None:
        self._window.clear()

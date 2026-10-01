"""Rolling monitor that tracks peak, count and filtered average."""

from __future__ import annotations

from portpower.cable.filter import MovingAverageFilter


class TemperatureMonitor:
    def __init__(self, window: int = 5) -> None:
        self._filter = MovingAverageFilter(window)
        self._peak = 0.0
        self._count = 0

    def observe(self, sample: float) -> float:
        self._filter.add(sample)
        if sample > self._peak:
            self._peak = float(sample)
        self._count += 1
        return self.filtered

    @property
    def filtered(self) -> float:
        return self._filter.average

    def summary(self) -> dict[str, float]:
        return {
            "peak": self._peak,
            "count": float(self._count),
            "average": self.filtered,
        }

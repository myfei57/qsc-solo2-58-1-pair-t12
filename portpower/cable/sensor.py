"""Single-value temperature sensor feeding the filter chain."""

from __future__ import annotations


class TemperatureSensor:
    def __init__(self, initial: float = 25.0) -> None:
        self._value = float(initial)

    def read(self) -> float:
        return self._value

    def set(self, value: float) -> float:
        self._value = float(value)
        return self._value

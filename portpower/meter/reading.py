"""Validated meter reading submitted by the field collector."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reading:
    berth: str
    timestamp: str
    value: float

    @classmethod
    def create(cls, berth: str, timestamp: str, value: float) -> "Reading":
        if not berth.strip():
            raise ValueError("berth is required")
        if not timestamp.strip():
            raise ValueError("timestamp is required")
        if value < 0:
            raise ValueError("value must not be negative")
        return cls(berth=berth.strip(), timestamp=timestamp.strip(), value=float(value))

    def describe(self) -> str:
        return f"{self.berth} {self.timestamp} {self.value:.2f}"

"""Tolerance window comparisons for grid frequency."""

from __future__ import annotations

DEFAULT_TARGET = 50.0
DEFAULT_TOLERANCE = 0.5


def in_band(current: float, target: float, tolerance: float) -> bool:
    if tolerance < 0:
        raise ValueError("tolerance must not be negative")
    return abs(current - target) <= tolerance


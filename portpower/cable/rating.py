"""Cable thermal classification derived from the latest sample."""

from __future__ import annotations

from enum import Enum


class Rating(str, Enum):
    NORMAL = "normal"
    WARM = "warm"
    HOT = "hot"

    @property
    def is_alarm(self) -> bool:
        return self is Rating.HOT


def classify(temperature: float, rated_temperature: float) -> Rating:
    if rated_temperature <= 0:
        raise ValueError("rated temperature must be positive")
    if temperature >= rated_temperature:
        return Rating.HOT
    if temperature >= rated_temperature * 0.8:
        return Rating.WARM
    return Rating.NORMAL

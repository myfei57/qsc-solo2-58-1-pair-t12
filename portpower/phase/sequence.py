"""The two phase rotations the shore supply may present."""

from __future__ import annotations

from enum import Enum


class Sequence(str, Enum):
    FORWARD = "ABC"
    REVERSE = "CBA"

"""Externally visible plug states."""

from __future__ import annotations

from enum import Enum


class PlugState(str, Enum):
    DISCONNECTED = "disconnected"
    ENGAGED = "engaged"

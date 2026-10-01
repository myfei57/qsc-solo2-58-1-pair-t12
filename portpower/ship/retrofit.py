"""Vessel retrofit operations that grow the declared load envelope."""

from __future__ import annotations

from portpower.ship.profile import Profile
from portpower.ship.registry import ProfileRegistry

MAX_ADDED_LOAD = 5000.0


def apply_retrofit(registry: ProfileRegistry, ship: str, added_load: float) -> Profile:
    if added_load <= 0:
        raise ValueError("added load must be positive")
    if added_load > MAX_ADDED_LOAD:
        raise ValueError("added load exceeds retrofit ceiling")
    return registry.retrofit(ship, added_load)

"""Load demand helpers built on top of the profile registry."""

from __future__ import annotations

from portpower.ship.registry import ProfileRegistry


def demand_of(registry: ProfileRegistry, ship: str) -> float:
    return registry.demand(ship)


def headroom_of(registry: ProfileRegistry, ship: str, factor: float = 1.1) -> float:
    return registry.headroom(ship, factor)

"""Load limit enforcement against the vessel's declared envelope."""

from __future__ import annotations

from portpower.ship.registry import ProfileRegistry


class LoadExceedsProfile(RuntimeError):
    """Raised when a requested load exceeds the vessel's declared envelope."""


class LimitEnforcer:
    def __init__(self, registry: ProfileRegistry) -> None:
        self._registry = registry

    def allow(self, ship: str, load: float) -> bool:
        profile = self._registry.load(ship)
        if profile is None:
            return False
        return load <= profile.max_load

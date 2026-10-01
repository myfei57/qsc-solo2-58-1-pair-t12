"""A vessel's declared energy budget and what it has consumed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Quota:
    ship: str
    limit: float
    used: float = 0.0

    @property
    def remaining(self) -> float:
        return self.limit - self.used

    def with_usage(self, amount: float) -> "Quota":
        return Quota(ship=self.ship, limit=self.limit, used=self.used + amount)

    def as_dict(self) -> dict[str, object]:
        return {"ship": self.ship, "limit": self.limit, "used": self.used}

    @classmethod
    def from_dict(cls, payload: object) -> "Quota | None":
        if not isinstance(payload, dict):
            return None
        ship = payload.get("ship")
        limit = payload.get("limit")
        used = payload.get("used", 0.0)
        if not isinstance(ship, str) or not ship:
            return None
        if not isinstance(limit, (int, float)) or not isinstance(used, (int, float)):
            return None
        return cls(ship=ship, limit=float(limit), used=float(used))

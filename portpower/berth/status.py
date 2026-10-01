"""Read models exposed by the berth endpoints."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from portpower.berth.berth import Berth


@dataclass(frozen=True)
class BerthStatus:
    code: str
    state: str
    ship: str | None = None

    @classmethod
    def from_berth(cls, berth: Berth) -> "BerthStatus":
        described = berth.describe()
        ship = described.get("ship")
        return cls(
            code=str(described["code"]),
            state=str(described["state"]),
            ship=ship if isinstance(ship, str) else None,
        )

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        if payload["ship"] is None:
            payload.pop("ship")
        return payload

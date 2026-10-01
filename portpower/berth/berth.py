"""Single berth and its two-state occupancy machine."""

from __future__ import annotations

from enum import Enum


class BerthOccupied(RuntimeError):
    """Raised when a ship is assigned to a berth that already holds one."""


class BerthVacant(RuntimeError):
    """Raised when an operation expects an occupied berth but finds none."""


class BerthState(str, Enum):
    FREE = "free"
    OCCUPIED = "occupied"


class Berth:
    def __init__(self, code: str) -> None:
        self.code = code
        self._ship_id: str | None = None

    @property
    def state(self) -> BerthState:
        return BerthState.OCCUPIED if self.occupied else BerthState.FREE

    @property
    def occupied(self) -> bool:
        return self._ship_id is not None

    @property
    def ship_id(self) -> str | None:
        return self._ship_id

    def assign(self, ship_id: str) -> None:
        if self.occupied:
            raise BerthOccupied(f"berth {self.code} already holds {self._ship_id}")
        if not ship_id.strip():
            raise ValueError("ship id is required")
        self._ship_id = ship_id

    def release(self) -> str:
        if not self.occupied:
            raise BerthVacant(f"berth {self.code} is already free")
        previous = self._ship_id
        self._ship_id = None
        return previous or ""

    def describe(self) -> dict[str, object]:
        payload: dict[str, object] = {"code": self.code, "state": self.state.value}
        if self._ship_id is not None:
            payload["ship"] = self._ship_id
        return payload

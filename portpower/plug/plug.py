"""Connector plug holding its engagement flag and bound vessel."""

from __future__ import annotations

from portpower.plug.state import PlugState


class Plug:
    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        self._engaged = False
        self._bound_ship: str | None = None

    @property
    def engaged(self) -> bool:
        return self._engaged

    @property
    def bound_ship(self) -> str | None:
        return self._bound_ship

    @property
    def state(self) -> PlugState:
        return PlugState.ENGAGED if self._engaged else PlugState.DISCONNECTED

    def mark_engaged(self, ship: str) -> None:
        self._engaged = True
        self._bound_ship = ship

    def mark_released(self) -> None:
        self._engaged = False
        self._bound_ship = None

    def describe(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.identifier,
            "state": self.state.value,
        }
        if self.bound_ship is not None:
            payload["bound_ship"] = self.bound_ship
        return payload

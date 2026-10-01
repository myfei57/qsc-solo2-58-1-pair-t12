"""Registry of vessels currently known to the harbour."""

from __future__ import annotations

from portpower.ship.ship import Ship


class Fleet:
    def __init__(self) -> None:
        self._ships: dict[str, Ship] = {}

    def add(self, identifier: str, name: str = "vessel") -> Ship:
        existing = self._ships.get(identifier)
        if existing is not None:
            return existing
        created = Ship(identifier, name)
        self._ships[identifier] = created
        return created

    def get(self, identifier: str) -> Ship | None:
        return self._ships.get(identifier)

    def identifiers(self) -> list[str]:
        return sorted(self._ships)

    def count(self) -> int:
        return len(self._ships)

    def moored(self) -> list[str]:
        return sorted(
            identifier
            for identifier, ship in self._ships.items()
            if ship.moored_at is not None
        )

    def undock(self, identifier: str) -> bool:
        ship = self._ships.get(identifier)
        if ship is None:
            return False
        ship.depart()
        return True

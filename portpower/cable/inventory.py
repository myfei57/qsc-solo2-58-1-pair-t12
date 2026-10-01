"""Cable inventory keyed by cable id."""

from __future__ import annotations

from portpower.cable.cable import Cable


class CableInventory:
    def __init__(self) -> None:
        self._cables: dict[str, Cable] = {}

    def add(self, identifier: str, rated_temperature: float) -> Cable:
        existing = self._cables.get(identifier)
        if existing is not None:
            return existing
        created = Cable(identifier, rated_temperature)
        self._cables[identifier] = created
        return created

    def get(self, identifier: str) -> Cable | None:
        return self._cables.get(identifier)

    def identifiers(self) -> list[str]:
        return sorted(self._cables)

    def count(self) -> int:
        return len(self._cables)

    def select(self, minimum_temperature: float) -> Cable | None:
        for identifier in self.identifiers():
            cable = self._cables[identifier]
            if cable.rated_temperature >= minimum_temperature:
                return cable
        return None

    def ratings(self) -> dict[str, float]:
        return {
            identifier: cable.rated_temperature
            for identifier, cable in self._cables.items()
        }

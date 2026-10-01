"""A vessel and the berth it currently occupies."""

from __future__ import annotations


class Ship:
    def __init__(self, identifier: str, name: str) -> None:
        self.identifier = identifier
        self.name = name
        self._berth: str | None = None

    @property
    def moored_at(self) -> str | None:
        return self._berth

    def moor(self, berth: str | None) -> None:
        self._berth = berth or None

    def depart(self) -> None:
        self._berth = None

    def describe(self) -> dict[str, object]:
        return {
            "id": self.identifier,
            "name": self.name,
            "berth": self._berth,
        }

"""A shore power cable and the temperature it is rated for."""

from __future__ import annotations


class Cable:
    def __init__(self, identifier: str, rated_temperature: float) -> None:
        if rated_temperature <= 0:
            raise ValueError("rated temperature must be positive")
        self.identifier = identifier
        self._rated_temperature = rated_temperature

    @property
    def rated_temperature(self) -> float:
        return self._rated_temperature

    def describe(self) -> dict[str, object]:
        return {"id": self.identifier, "rated_temperature": self._rated_temperature}

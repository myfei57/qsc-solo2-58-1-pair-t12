"""In-memory registry of berths keyed by code."""

from __future__ import annotations

from portpower.berth.berth import Berth, BerthVacant
from portpower.berth.status import BerthStatus


class NoBerthAvailable(RuntimeError):
    """Raised when every berth in the registry already holds a vessel."""


class BerthRegistry:
    def __init__(self) -> None:
        self._berths: dict[str, Berth] = {}

    def add(self, code: str) -> Berth:
        existing = self._berths.get(code)
        if existing is not None:
            return existing
        created = Berth(code)
        self._berths[code] = created
        return created

    def get(self, code: str) -> Berth | None:
        return self._berths.get(code)

    def codes(self) -> list[str]:
        return sorted(self._berths)

    def occupied_count(self) -> int:
        return sum(1 for berth in self._berths.values() if berth.occupied)

    def release(self, code: str) -> bool:
        berth = self._berths.get(code)
        if berth is None:
            return False
        try:
            berth.release()
        except BerthVacant:
            return False
        return True

    def ship_at(self, code: str) -> str | None:
        berth = self._berths.get(code)
        if berth is None or not berth.occupied:
            return None
        return berth.ship_id

    def status_all(self) -> list[BerthStatus]:
        return [BerthStatus.from_berth(self._berths[code]) for code in self.codes()]

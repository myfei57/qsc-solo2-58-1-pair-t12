"""Physical meter attached to a single berth."""

from __future__ import annotations

from portpower.store.kvstore import RecordStore

FREEZE_PREFIX = "meter.frozen."


class MeterFrozen(RuntimeError):
    """Raised when a reading is submitted for a frozen meter."""


def freeze_key(berth: str) -> str:
    return FREEZE_PREFIX + berth


class Meter:
    def __init__(
        self,
        identifier: str,
        berth: str,
        store: RecordStore | None = None,
    ) -> None:
        self.identifier = identifier
        self.berth = berth
        self._store = store
        self._frozen = False

    @property
    def store(self) -> RecordStore | None:
        return self._store

    @property
    def frozen(self) -> bool:
        if self._frozen:
            return True
        if self._store is not None and self._store.has(freeze_key(self.berth)):
            return True
        return False

    def mark_frozen(self) -> None:
        self._frozen = True

    def clear_frozen(self) -> None:
        self._frozen = False

    def describe(self) -> dict[str, object]:
        return {
            "id": self.identifier,
            "berth": self.berth,
            "frozen": self.frozen,
        }

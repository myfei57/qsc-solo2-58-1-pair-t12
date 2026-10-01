"""Berth reservation windows with overlap detection."""

from __future__ import annotations

from dataclasses import dataclass

from portpower.store.kvstore import RecordStore

PREFIX = "berth.reservation."


def reservation_key(code: str) -> str:
    return PREFIX + code


@dataclass(frozen=True)
class Reservation:
    berth: str
    ship: str
    start: str
    end: str

    def __post_init__(self) -> None:
        if not self.berth.strip():
            raise ValueError("reservation berth is required")
        if not self.ship.strip():
            raise ValueError("reservation ship is required")
        if self.start >= self.end:
            raise ValueError("reservation window is inverted")

    def overlaps(self, other: "Reservation") -> bool:
        if self.berth != other.berth:
            return False
        return self.start < other.end and other.start < self.end

    def as_dict(self) -> dict[str, str]:
        return {
            "berth": self.berth,
            "ship": self.ship,
            "start": self.start,
            "end": self.end,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "Reservation | None":
        if not isinstance(payload, dict):
            return None
        try:
            return cls(
                berth=str(payload["berth"]),
                ship=str(payload["ship"]),
                start=str(payload["start"]),
                end=str(payload["end"]),
            )
        except (KeyError, ValueError):
            return None


class ReservationConflict(RuntimeError):
    """Raised when a booking overlaps an existing window on the same berth."""


class Scheduler:
    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def book(self, reservation: Reservation) -> None:
        existing = self.get(reservation.berth)
        if existing is not None and existing.overlaps(reservation):
            raise ReservationConflict(
                f"berth {reservation.berth} busy {existing.start}..{existing.end}"
            )
        self._store.put_json(reservation_key(reservation.berth), reservation.as_dict())

    def get(self, berth: str) -> Reservation | None:
        return Reservation.from_dict(self._store.get_json(reservation_key(berth)))

    def cancel(self, berth: str) -> None:
        self._store.delete(reservation_key(berth))

    def list_all(self) -> list[Reservation]:
        from portpower.store.query import keys_with_prefix

        items: list[Reservation] = []
        for key in keys_with_prefix(self._store, PREFIX):
            reservation = self.get(key[len(PREFIX) :])
            if reservation is not None:
                items.append(reservation)
        items.sort(key=lambda item: (item.berth, item.start))
        return items

    def count(self) -> int:
        return len(self.list_all())

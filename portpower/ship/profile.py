"""Declared power envelope for a vessel."""

from __future__ import annotations

from dataclasses import asdict, dataclass

VALID_SEQUENCES = ("ABC", "CBA")


@dataclass(frozen=True)
class Profile:
    ship: str
    max_load: float
    phase_seq: str
    frequency: float

    def valid(self) -> bool:
        return bool(self.ship.strip()) and self.max_load > 0 and self.frequency > 0

    def phase_valid(self) -> bool:
        return self.phase_seq in VALID_SEQUENCES

    def is_usable(self) -> bool:
        return self.valid() and self.phase_valid()

    def with_added_load(self, added: float) -> "Profile":
        return Profile(
            ship=self.ship,
            max_load=self.max_load + added,
            phase_seq=self.phase_seq,
            frequency=self.frequency,
        )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: object) -> "Profile | None":
        if not isinstance(payload, dict):
            return None
        try:
            return cls(
                ship=str(payload["ship"]),
                max_load=float(payload["max_load"]),
                phase_seq=str(payload["phase_seq"]),
                frequency=float(payload["frequency"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

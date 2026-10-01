"""Versioned history of every profile a vessel has announced."""

from __future__ import annotations

from dataclasses import dataclass

from portpower.ship.profile import Profile
from portpower.store.kvstore import RecordStore

PREFIX = "ship.history."


def history_key(ship: str) -> str:
    return PREFIX + ship


@dataclass(frozen=True)
class ProfileRecord:
    version: int
    profile: Profile

    def as_dict(self) -> dict[str, object]:
        payload = {"version": self.version}
        payload.update(self.profile.as_dict())
        return payload

    @classmethod
    def from_dict(cls, payload: object) -> "ProfileRecord | None":
        if not isinstance(payload, dict):
            return None
        profile = Profile.from_dict(payload)
        version = payload.get("version")
        if profile is None or not isinstance(version, int):
            return None
        return cls(version=version, profile=profile)


class ProfileHistory:
    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def append(self, profile: Profile) -> ProfileRecord:
        records = self.list_for(profile.ship)
        version = records[-1].version + 1 if records else 1
        record = ProfileRecord(version=version, profile=profile)
        records.append(record)
        self._store.put_json(
            history_key(profile.ship), [item.as_dict() for item in records]
        )
        return record

    def list_for(self, ship: str) -> list[ProfileRecord]:
        payload = self._store.get_json(history_key(ship))
        if not isinstance(payload, list):
            return []
        records: list[ProfileRecord] = []
        for item in payload:
            record = ProfileRecord.from_dict(item)
            if record is not None:
                records.append(record)
        records.sort(key=lambda item: item.version)
        return records

    def latest(self, ship: str) -> ProfileRecord | None:
        records = self.list_for(ship)
        return records[-1] if records else None

    def count(self, ship: str) -> int:
        return len(self.list_for(ship))

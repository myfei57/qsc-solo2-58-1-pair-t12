"""Durable store of the most recent profile for each vessel."""

from __future__ import annotations

from portpower.ship.profile import Profile
from portpower.store.kvstore import RecordStore

PREFIX = "ship.profile."


def profile_key(ship: str) -> str:
    return PREFIX + ship


class ProfileRegistry:
    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def save(self, profile: Profile) -> None:
        self._store.put_json(profile_key(profile.ship), profile.as_dict())

    def load(self, ship: str) -> Profile | None:
        return Profile.from_dict(self._store.get_json(profile_key(ship)))

    def known_ships(self) -> list[str]:
        from portpower.store.query import keys_with_prefix

        return [key[len(PREFIX) :] for key in keys_with_prefix(self._store, PREFIX)]

    def demand(self, ship: str) -> float:
        profile = self.load(ship)
        return profile.max_load if profile is not None else 0.0

    def headroom(self, ship: str, factor: float = 1.1) -> float:
        return self.demand(ship) * factor

    def retrofit(self, ship: str, added_load: float) -> Profile:
        profile = self.load(ship)
        if profile is None:
            raise LookupError(f"profile not found for ship {ship}")
        updated = profile.with_added_load(added_load)
        self.save(updated)
        return updated

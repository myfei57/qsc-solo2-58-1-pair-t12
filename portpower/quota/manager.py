"""Durable quota ledger keyed by vessel."""

from __future__ import annotations

from portpower.quota.quota import Quota
from portpower.store.kvstore import RecordStore

PREFIX = "quota."


def quota_key(ship: str) -> str:
    return PREFIX + ship


class QuotaManager:
    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def set(self, quota: Quota) -> None:
        self._store.put_json(quota_key(quota.ship), quota.as_dict())

    def get(self, ship: str) -> Quota | None:
        return Quota.from_dict(self._store.get_json(quota_key(ship)))

    def all(self) -> dict[str, Quota]:
        from portpower.store.query import keys_with_prefix

        out: dict[str, Quota] = {}
        for key in keys_with_prefix(self._store, PREFIX):
            ship = key[len(PREFIX) :]
            quota = self.get(ship)
            if quota is not None:
                out[ship] = quota
        return out

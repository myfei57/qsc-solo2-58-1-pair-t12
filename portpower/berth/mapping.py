"""Durable berth-to-ship mapping that survives restarts."""

from __future__ import annotations

from portpower.store.kvstore import RecordStore

PREFIX = "berth.mapping."


def mapping_key(code: str) -> str:
    return PREFIX + code


class BerthMapping:
    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def bind(self, code: str, ship_id: str) -> None:
        self._store.put_json(mapping_key(code), ship_id)

    def ship_for(self, code: str) -> str | None:
        value = self._store.get_json(mapping_key(code))
        return value if isinstance(value, str) and value else None

    def unbind(self, code: str) -> None:
        self._store.delete(mapping_key(code))

    def entries(self) -> dict[str, str]:
        from portpower.store.query import keys_with_prefix

        out: dict[str, str] = {}
        for key in keys_with_prefix(self._store, PREFIX):
            ship_id = self.ship_for(key[len(PREFIX) :])
            if ship_id is not None:
                out[key[len(PREFIX) :]] = ship_id
        return out

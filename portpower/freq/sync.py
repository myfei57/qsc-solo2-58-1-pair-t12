"""Durable current-frequency value shared across restarts."""

from __future__ import annotations

from portpower.store.kvstore import RecordStore

CURRENT_KEY = "freq.current"


def set_current(store: RecordStore, value: float) -> float:
    store.put_json(CURRENT_KEY, float(value))
    return float(value)


def read_current(store: RecordStore) -> float | None:
    value = store.get_json(CURRENT_KEY)
    if isinstance(value, (int, float)):
        return float(value)
    return None

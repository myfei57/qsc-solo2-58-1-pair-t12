"""Cheap aggregate metrics over the record store."""

from __future__ import annotations

from portpower.store.kvstore import RecordStore


def key_count(store: RecordStore) -> int:
    with store.transaction() as data:
        return len(data)


def total_bytes(store: RecordStore) -> int:
    with store.transaction() as data:
        return sum(len(value) for value in data.values())


def largest_key(store: RecordStore) -> str | None:
    with store.transaction() as data:
        if not data:
            return None
        return max(data, key=lambda key: len(data[key]))

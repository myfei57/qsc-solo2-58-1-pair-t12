"""Prefix based lookups over the record store."""

from __future__ import annotations

from portpower.store.kvstore import RecordStore


def keys_with_prefix(store: RecordStore, prefix: str) -> list[str]:
    with store.transaction() as data:
        matched = [key for key in data if key.startswith(prefix)]
    matched.sort()
    return matched


def count_with_prefix(store: RecordStore, prefix: str) -> int:
    with store.transaction() as data:
        return sum(1 for key in data if key.startswith(prefix))

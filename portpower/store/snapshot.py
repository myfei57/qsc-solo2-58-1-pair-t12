"""Whole-store export and import helpers."""

from __future__ import annotations

import json
from typing import Any

from portpower.store.kvstore import RecordStore, encode


def export_snapshot(store: RecordStore) -> dict[str, Any]:
    with store.transaction() as data:
        return {key: json.loads(value.decode("utf-8")) for key, value in data.items()}


def import_snapshot(store: RecordStore, payload: dict[str, Any]) -> int:
    """Replace the store contents with ``payload`` and return the key count."""

    if not isinstance(payload, dict):
        raise ValueError("snapshot payload must be an object")
    with store.transaction() as data:
        existing = list(data)
    for key in existing:
        store.delete(key)
    for key, value in payload.items():
        store.put(key, encode(value))
    return len(payload)

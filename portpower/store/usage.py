"""Append-only usage ledger with timestamp de-duplication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from portpower.store.kvstore import RecordStore

USAGE_KEY = "meter.usage"


@dataclass(frozen=True)
class UsageEntry:
    timestamp: str
    value: float


class UsageLog:
    """Stores one reading per timestamp so retries never double count."""

    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def append_once(self, timestamp: str, value: float) -> bool:
        def mutate(document: Any) -> tuple[Any, bool]:
            records = _normalize(document)
            if any(item["timestamp"] == timestamp for item in records):
                return None, False
            records.append({"timestamp": timestamp, "value": float(value)})
            return {"records": records}, True

        return self._store.update_json(USAGE_KEY, mutate)

    def entries(self) -> list[UsageEntry]:
        document = self._store.get_json(USAGE_KEY)
        records = _normalize(document)
        entries = [UsageEntry(item["timestamp"], float(item["value"])) for item in records]
        entries.sort(key=lambda item: item.timestamp)
        return entries

    def total(self) -> float:
        return sum(item.value for item in self.entries())

    def between(self, start: str, end: str) -> list[UsageEntry]:
        return [item for item in self.entries() if start <= item.timestamp <= end]

    def timestamps(self) -> list[str]:
        return [item.timestamp for item in self.entries()]


def _normalize(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict):
        return []
    records = document.get("records")
    if not isinstance(records, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        timestamp = item.get("timestamp")
        value = item.get("value")
        if isinstance(timestamp, str) and isinstance(value, (int, float)):
            cleaned.append({"timestamp": timestamp, "value": float(value)})
    return cleaned

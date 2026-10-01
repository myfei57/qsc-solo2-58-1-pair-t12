"""Durable audit ledger with monotonic timestamps."""

from __future__ import annotations

from datetime import datetime, timezone

from portpower.audit.entry import AuditEntry
from portpower.store.kvstore import RecordStore

LEDGER_KEY = "audit.log"


class Ledger:
    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def append(self, event: str, detail: str) -> AuditEntry:
        entry = AuditEntry(at=_timestamp(), event=event, detail=detail)

        def mutate(document: object) -> tuple[object, AuditEntry]:
            entries = self._normalize(document)
            entries.append(entry)
            return [item.as_dict() for item in entries], entry

        return self._store.update_json(LEDGER_KEY, mutate)

    def entries(self) -> list[AuditEntry]:
        return self._normalize(self._store.get_json(LEDGER_KEY))

    def latest(self) -> AuditEntry | None:
        entries = self.entries()
        return entries[-1] if entries else None

    def count(self) -> int:
        return len(self.entries())

    @staticmethod
    def _normalize(document: object) -> list[AuditEntry]:
        if not isinstance(document, list):
            return []
        entries: list[AuditEntry] = []
        for item in document:
            entry = AuditEntry.from_dict(item)
            if entry is not None:
                entries.append(entry)
        entries.sort(key=lambda item: item.at)
        return entries


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

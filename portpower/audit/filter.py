"""Ledger projections by event name."""

from __future__ import annotations

from portpower.audit.entry import AuditEntry
from portpower.audit.ledger import Ledger


def by_event(ledger: Ledger, event: str) -> list[AuditEntry]:
    return [entry for entry in ledger.entries() if entry.event == event]


def events(ledger: Ledger) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in ledger.entries():
        if entry.event in seen:
            continue
        seen.add(entry.event)
        ordered.append(entry.event)
    return ordered


def tail(ledger: Ledger, limit: int) -> list[AuditEntry]:
    if limit <= 0:
        return []
    return ledger.entries()[-limit:]

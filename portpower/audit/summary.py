"""Aggregate counts over the audit ledger."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from portpower.audit.ledger import Ledger


@dataclass(frozen=True)
class Summary:
    total: int
    by_event: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def summarize(ledger: Ledger) -> Summary:
    by_event: dict[str, int] = {}
    total = 0
    for entry in ledger.entries():
        total += 1
        by_event[entry.event] = by_event.get(entry.event, 0) + 1
    return Summary(total=total, by_event=by_event)

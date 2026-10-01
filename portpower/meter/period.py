"""Aggregation of usage readings inside a timestamp window."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from portpower.store.kvstore import RecordStore
from portpower.store.usage import UsageLog


@dataclass(frozen=True)
class Period:
    start: str
    end: str
    total: float
    count: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def aggregate(store: RecordStore, start: str, end: str) -> Period:
    entries = UsageLog(store).between(start, end)
    return Period(
        start=start,
        end=end,
        total=sum(entry.value for entry in entries),
        count=len(entries),
    )

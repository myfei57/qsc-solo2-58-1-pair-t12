"""Collector that funnels readings through the de-duplicating usage log."""

from __future__ import annotations

from portpower.meter.reading import Reading
from portpower.store.kvstore import RecordStore
from portpower.store.usage import UsageLog


class Collector:
    def __init__(self, store: RecordStore) -> None:
        self._log = UsageLog(store)

    def record(self, reading: Reading) -> bool:
        return self._log.append_once(reading.timestamp, reading.value)

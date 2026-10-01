"""Tariff application over accumulated usage."""

from __future__ import annotations

from portpower.store.kvstore import RecordStore
from portpower.store.usage import UsageLog

DEFAULT_RATE = 0.95


class Tariff:
    def __init__(self, rate: float = DEFAULT_RATE) -> None:
        if rate < 0:
            raise ValueError("tariff rate must not be negative")
        self.rate = float(rate)

    def charge(self, total: float) -> float:
        return total * self.rate


def total_usage(store: RecordStore) -> float:
    return UsageLog(store).total()

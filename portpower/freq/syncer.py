"""Synchroniser that keeps the durable value and in-process fallback aligned."""

from __future__ import annotations

from portpower.freq.band import DEFAULT_TARGET, in_band
from portpower.freq.samples import SampleLog
from portpower.freq.sync import read_current, set_current
from portpower.store.kvstore import RecordStore


class Syncer:
    def __init__(self, store: RecordStore, initial: float = DEFAULT_TARGET) -> None:
        self._store = store
        self._fallback = float(initial)
        self._samples = SampleLog(store)

    @property
    def current(self) -> float:
        stored = read_current(self._store)
        return stored if stored is not None else self._fallback

    def refresh(self, value: float) -> float:
        self._fallback = set_current(self._store, value)
        return self._fallback

    def record_sample(self, value: float) -> list[float]:
        return self._samples.record(value)

    def samples(self) -> list[float]:
        return self._samples.samples()

    def average(self) -> float:
        return self._samples.average()

    def latest_sample(self) -> float | None:
        return self._samples.latest

    def within(self, target: float = DEFAULT_TARGET, tolerance: float = 0.5) -> bool:
        return in_band(self.current, target, tolerance)

    def stable(self, target: float = DEFAULT_TARGET, tolerance: float = 0.5) -> bool:
        return self._samples.stable(target, tolerance)

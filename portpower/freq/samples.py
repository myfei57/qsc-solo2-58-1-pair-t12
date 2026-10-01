"""Rolling log of every frequency sample pushed by the field bus."""

from __future__ import annotations

from portpower.freq.band import DEFAULT_TARGET, DEFAULT_TOLERANCE, in_band
from portpower.store.kvstore import RecordStore

SAMPLES_KEY = "freq.samples"
MAX_SAMPLES = 512


class SampleLog:
    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def record(self, value: float) -> list[float]:
        def mutate(document: object) -> tuple[object, list[float]]:
            samples = _normalize(document)
            samples.append(float(value))
            trimmed = samples[-MAX_SAMPLES:]
            return trimmed, trimmed

        return self._store.update_json(SAMPLES_KEY, mutate)

    def samples(self) -> list[float]:
        return _normalize(self._store.get_json(SAMPLES_KEY))

    @property
    def latest(self) -> float | None:
        samples = self.samples()
        return samples[-1] if samples else None

    def average(self) -> float:
        samples = self.samples()
        return sum(samples) / len(samples) if samples else 0.0

    def stable(self, target: float = DEFAULT_TARGET, tolerance: float = DEFAULT_TOLERANCE) -> bool:
        samples = self.samples()
        if not samples:
            return False
        return all(in_band(sample, target, tolerance) for sample in samples[-5:])


def _normalize(document: object) -> list[float]:
    if not isinstance(document, list):
        return []
    return [float(item) for item in document if isinstance(item, (int, float))]

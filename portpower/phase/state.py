"""Rolling phase state that remembers the recent rotations seen."""

from __future__ import annotations

from portpower.phase.sequence import Sequence


class PhaseState:
    def __init__(self, initial: Sequence = Sequence.FORWARD, keep: int = 16) -> None:
        self._current = initial
        self._history: list[Sequence] = [initial]
        self._keep = max(1, keep)

    @property
    def current(self) -> Sequence:
        return self._current

    def history(self) -> list[Sequence]:
        return list(self._history)

    def set(self, sequence: Sequence) -> None:
        self._current = sequence
        self._history.append(sequence)
        if len(self._history) > self._keep:
            del self._history[: len(self._history) - self._keep]

    @property
    def reversed(self) -> bool:
        return self._current is Sequence.REVERSE

    def flips(self) -> int:
        return sum(
            1
            for previous, current in zip(self._history, self._history[1:])
            if previous is not current
        )

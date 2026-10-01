"""Verification that the shore supply presents a forward rotation."""

from __future__ import annotations

from portpower.phase.sequence import Sequence


class PhaseReversed(RuntimeError):
    """Raised when the supply rotation would drive the vessel backwards."""


class Verifier:
    def __init__(self, sequence: Sequence) -> None:
        self._sequence = sequence

    @property
    def sequence(self) -> Sequence:
        return self._sequence

    @property
    def is_forward(self) -> bool:
        return self._sequence is Sequence.FORWARD

    def verify(self) -> None:
        if not self.is_forward:
            raise PhaseReversed("reversed phase sequence")

    def is_valid(self) -> bool:
        try:
            self.verify()
        except PhaseReversed:
            return False
        return True

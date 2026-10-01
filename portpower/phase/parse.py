"""Mapping of operator supplied text onto a phase sequence."""

from __future__ import annotations

from portpower.phase.sequence import Sequence

_ALIASES = {
    "ABC": Sequence.FORWARD,
    "CBA": Sequence.REVERSE,
}


def parse_sequence(value: str) -> Sequence | None:
    return _ALIASES.get(value.strip().upper())

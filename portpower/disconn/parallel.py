"""Parallel close gated on the frequency synchronisation window."""

from __future__ import annotations

from portpower.disconn.breaker import Breaker
from portpower.freq.band import DEFAULT_TARGET, DEFAULT_TOLERANCE, in_band
from portpower.freq.syncer import Syncer


class FrequencyOutOfSync(RuntimeError):
    """Raised when the grid frequency is outside the close window."""


def parallel_close(
    breaker: Breaker,
    syncer: Syncer,
    target: float = DEFAULT_TARGET,
    tolerance: float = DEFAULT_TOLERANCE,
) -> float:
    current = syncer.current
    if not in_band(current, target, tolerance):
        raise FrequencyOutOfSync(
            f"frequency {current:.3f} outside {target:.3f}+-{tolerance:.3f}"
        )
    breaker.mark_closed()
    return current

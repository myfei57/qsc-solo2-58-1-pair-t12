"""Closing the breaker only after the upstream interlocks clear."""

from __future__ import annotations

from portpower.disconn.breaker import Breaker
from portpower.phase.verifier import Verifier
from portpower.ship.arm import BreakerArm


class ArmMissing(RuntimeError):
    """Raised when the vessel breaker has not been armed."""


def close_after_phase(breaker: Breaker, verifier: Verifier) -> None:
    verifier.verify()
    breaker.mark_closed()


def close_after_arm(breaker: Breaker, arm: BreakerArm) -> None:
    if not arm.armed:
        raise ArmMissing("ship breaker not armed")
    breaker.mark_closed()

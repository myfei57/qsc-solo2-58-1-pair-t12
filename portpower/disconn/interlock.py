"""Composite interlock combining arming and phase verification."""

from __future__ import annotations

from portpower.disconn.breaker import Breaker
from portpower.phase.verifier import Verifier
from portpower.ship.arm import BreakerArm


def interlock_ready(breaker: Breaker, arm: BreakerArm, verifier: Verifier) -> bool:
    if breaker.tripped:
        return False
    if not arm.armed:
        return False
    return verifier.is_valid()

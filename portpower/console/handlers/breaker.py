"""Breaker state, trip, reset and interlock endpoints."""

from __future__ import annotations

from portpower.console.http import Request, Response
from portpower.disconn.interlock import interlock_ready
from portpower.disconn.trip import reset_breaker, trip_breaker
from portpower.phase.verifier import Verifier
from portpower.ship.arm import BreakerArm


def breaker_state(runtime, request: Request) -> Response:
    return Response.json(
        200,
        {
            "breaker": runtime.shore.describe(),
            "state": runtime.shore.state.value,
            "conducts": runtime.shore.state.conducts,
        },
    )


def breaker_trip(runtime, request: Request) -> Response:
    trip_breaker(runtime.shore)
    return Response.json(
        200,
        {"tripped": runtime.shore.tripped, "state": runtime.shore.state.value},
    )


def breaker_reset(runtime, request: Request) -> Response:
    reset_breaker(runtime.shore)
    return Response.json(
        200,
        {"closed": runtime.shore.closed, "state": runtime.shore.state.value},
    )


def breaker_interlock(runtime, request: Request) -> Response:
    arm = BreakerArm()
    arm.arm()
    verifier = Verifier(runtime.phase.current)
    return Response.json(
        200,
        {
            "ready": interlock_ready(runtime.shore, arm, verifier),
            "armed": arm.armed,
            "phase": verifier.sequence.value,
            "forward": verifier.is_forward,
        },
    )

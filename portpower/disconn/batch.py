"""Ordered disconnect chain shared by the离泊 and batch endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from portpower.disconn.breaker import Breaker
from portpower.disconn.open import open_breaker
from portpower.meter.binder import Binder


@dataclass(frozen=True)
class Connection:
    breaker: Breaker
    binder: Binder
    berth: str


@dataclass(frozen=True)
class DisconnectStep:
    berth: str
    opened: bool
    final_value: float


def batch_disconnect(
    connections: list[Connection],
    final_values: dict[str, float],
) -> list[DisconnectStep]:
    steps: list[DisconnectStep] = []
    for connection in connections:
        open_breaker(connection.breaker)
        final = connection.binder.record_final(
            connection.berth, final_values.get(connection.berth, 0.0)
        )
        connection.binder.unbind(connection.berth)
        steps.append(
            DisconnectStep(
                berth=connection.berth,
                opened=True,
                final_value=final,
            )
        )
    return steps

"""Departure sequence: open, freeze, unbind and release."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from portpower.console.validation import optional_number, optional_text, require_text
from portpower.disconn.batch import Connection, batch_disconnect
from portpower.disconn.close import close_after_arm
from portpower.meter.binder import BindingMissing
from portpower.meter.freeze import freeze
from portpower.meter.meter import Meter
from portpower.plug.engage import engage
from portpower.plug.plug import Plug
from portpower.plug.release import release
from portpower.ship.arm import BreakerArm


@dataclass(frozen=True)
class DisconnectRequest:
    berth: str
    ship: str
    final_value: float
    connection_id: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "DisconnectRequest":
        return cls(
            berth=require_text(payload, "berth"),
            ship=optional_text(payload, "ship"),
            final_value=optional_number(payload, "final_value", 0.0),
            connection_id=optional_text(payload, "connection", "disconnect"),
        )


@dataclass(frozen=True)
class DisconnectResult:
    berth: str
    ship: str
    final_value: float | None
    released: bool
    breaker_state: str
    frozen: bool
    steps: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def run_disconnect(runtime, request: DisconnectRequest) -> DisconnectResult:
    binding = runtime.binder.load(request.berth)
    if binding is None:
        raise BindingMissing(f"no meter binding for berth {request.berth}")
    ship = request.ship or binding.ship

    arm = BreakerArm()
    arm.arm()
    close_after_arm(runtime.shore, arm)

    connector = Plug(request.connection_id)
    engage(connector, request.berth, runtime.binder)

    steps = batch_disconnect(
        [Connection(breaker=runtime.shore, binder=runtime.binder, berth=request.berth)],
        {request.berth: request.final_value},
    )

    meter = Meter(f"meter-{request.berth}", request.berth, runtime.store)
    frozen = freeze(meter)

    berth = runtime.berths.get(request.berth)
    if berth is not None and berth.ship_id == ship:
        runtime.berths.release(request.berth)
    runtime.fleet.undock(ship)
    runtime.mapping.unbind(request.berth)

    release(connector)
    runtime.protector.open_and_reset(runtime.shore)
    runtime.ledger.append(
        "disconnect",
        f"{runtime.harbor.qualified(request.berth)} {ship}",
    )

    return DisconnectResult(
        berth=request.berth,
        ship=ship,
        final_value=runtime.binder.final_value(request.berth),
        released=not connector.engaged,
        breaker_state=runtime.shore.state.value,
        frozen=frozen,
        steps=len(steps),
    )

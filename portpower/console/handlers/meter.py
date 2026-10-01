"""Meter reading, usage, billing and freeze endpoints."""

from __future__ import annotations

from portpower.console.http import Request, Response
from portpower.console.validation import require_number, require_text
from portpower.meter.binder import BindingMissing
from portpower.meter.collector import Collector
from portpower.meter.freeze import freeze, is_frozen, unfreeze
from portpower.meter.meter import Meter, MeterFrozen
from portpower.meter.period import aggregate
from portpower.meter.reading import Reading
from portpower.meter.tariff import total_usage
from portpower.store.usage import UsageLog


def record_reading(runtime, request: Request) -> Response:
    payload = request.json_object()
    reading = Reading.create(
        require_text(payload, "berth"),
        require_text(payload, "timestamp"),
        require_number(payload, "value"),
    )
    meter = Meter(f"meter-{reading.berth}", reading.berth, runtime.store)
    if is_frozen(meter):
        raise MeterFrozen(f"meter for berth {reading.berth} is frozen")
    if runtime.binder.load(reading.berth) is None:
        raise BindingMissing(f"no meter binding for berth {reading.berth}")
    recorded = Collector(runtime.store).record(reading)
    return Response.json(
        200,
        {
            "recorded": recorded,
            "duplicate": not recorded,
            "reading": reading.describe(),
        },
    )


def usage(runtime, request: Request) -> Response:
    log = UsageLog(runtime.store)
    timestamps = log.timestamps()
    return Response.json(
        200,
        {
            "total": log.total(),
            "readings": len(timestamps),
            "recent": timestamps[-5:],
        },
    )


def billing(runtime, request: Request) -> Response:
    total = total_usage(runtime.store)
    return Response.json(
        200,
        {
            "total_usage": total,
            "rate": runtime.tariff.rate,
            "charge": round(runtime.tariff.charge(total), 2),
        },
    )


def period(runtime, request: Request) -> Response:
    start = request.query_one("start", "") or ""
    end = request.query_one("end", "") or ""
    return Response.json(200, aggregate(runtime.store, start, end).as_dict())


def freeze_meter(runtime, request: Request) -> Response:
    payload = request.json_object()
    berth = require_text(payload, "berth")
    meter = Meter(f"meter-{berth}", berth, runtime.store)
    freeze(meter)
    return Response.json(200, meter.describe())


def unfreeze_meter(runtime, request: Request) -> Response:
    payload = request.json_object()
    berth = require_text(payload, "berth")
    meter = Meter(f"meter-{berth}", berth, runtime.store)
    unfreeze(meter)
    return Response.json(200, meter.describe())

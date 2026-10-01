"""Berth inventory, occupancy and allocation endpoints."""

from __future__ import annotations

from portpower.berth.assignment import allocate as allocate_berth
from portpower.berth.assignment import occupant, vacate
from portpower.berth.registry import NoBerthAvailable
from portpower.console.http import Request, Response
from portpower.console.validation import require_text


def berths(runtime, request: Request) -> Response:
    entries = runtime.mapping.entries()
    return Response.json(200, {"count": len(entries), "berths": entries})


def berth_status(runtime, request: Request) -> Response:
    statuses = runtime.berths.status_all()
    return Response.json(
        200,
        {
            "occupied_count": runtime.berths.occupied_count(),
            "count": len(statuses),
            "berths": [item.as_dict() for item in statuses],
        },
    )


def berth_detail(runtime, request: Request) -> Response:
    code = request.query_one("berth", "") or ""
    berth = runtime.berths.get(code)
    if berth is None:
        raise LookupError(f"unknown berth {code!r}")
    return Response.json(200, berth.describe())


def allocate(runtime, request: Request) -> Response:
    payload = request.json_object()
    ship = require_text(payload, "ship")
    code = allocate_berth(runtime.berths, runtime.catalog, ship)
    if code is None:
        raise NoBerthAvailable("no berth available")
    runtime.fleet.add(ship).moor(code)
    return Response.json(200, {"berth": code})


def release_berth(runtime, request: Request) -> Response:
    payload = request.json_object()
    code = require_text(payload, "berth")
    ship = occupant(runtime.berths, code)
    if ship is not None:
        runtime.fleet.undock(ship)
    return Response.json(200, {"vacated": vacate(runtime.berths, code)})

"""Vessel listing, retrofit and profile history endpoints."""

from __future__ import annotations

from portpower.console.http import Request, Response
from portpower.console.validation import require_number, require_text
from portpower.ship.demand import demand_of, headroom_of
from portpower.ship.retrofit import apply_retrofit


def ships(runtime, request: Request) -> Response:
    identifiers = runtime.fleet.identifiers()
    profiles: dict[str, object] = {}
    demand: dict[str, float] = {}
    headroom: dict[str, float] = {}
    for identifier in identifiers:
        profile = runtime.profiles.load(identifier)
        if profile is not None:
            profiles[identifier] = profile.as_dict()
        demand[identifier] = demand_of(runtime.profiles, identifier)
        headroom[identifier] = headroom_of(runtime.profiles, identifier)
    return Response.json(
        200,
        {
            "count": runtime.fleet.count(),
            "ship_ids": identifiers,
            "moored": runtime.fleet.moored(),
            "known_profiles": runtime.profiles.known_ships(),
            "profiles": profiles,
            "demand": demand,
            "headroom": headroom,
        },
    )


def ship_detail(runtime, request: Request) -> Response:
    identifier = request.query_one("ship", "") or ""
    ship = runtime.fleet.get(identifier)
    if ship is None:
        raise LookupError(f"unknown ship {identifier!r}")
    return Response.json(200, ship.describe())


def retrofit(runtime, request: Request) -> Response:
    payload = request.json_object()
    ship = require_text(payload, "ship")
    added = require_number(payload, "added_load")
    profile = apply_retrofit(runtime.profiles, ship, added)
    runtime.history.append(profile)
    return Response.json(
        200,
        {
            "retrofitted": True,
            "ship": ship,
            "max_load": profile.max_load,
            "versions": runtime.history.count(ship),
        },
    )


def history(runtime, request: Request) -> Response:
    ship = request.query_one("ship", "") or ""
    records = runtime.history.list_for(ship)
    latest = runtime.history.latest(ship)
    return Response.json(
        200,
        {
            "ship": ship,
            "count": len(records),
            "latest": latest.as_dict() if latest is not None else None,
            "records": [item.as_dict() for item in records],
        },
    )

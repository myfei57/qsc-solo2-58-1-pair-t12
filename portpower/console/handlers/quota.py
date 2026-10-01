"""Energy quota endpoints."""

from __future__ import annotations

from portpower.console.http import Request, Response
from portpower.console.validation import optional_number, require_number, require_text
from portpower.quota.enforce import remaining
from portpower.quota.quota import Quota
from portpower.quota.reserve import release, reserve


def quota_list(runtime, request: Request) -> Response:
    quotas = runtime.quotas.all()
    return Response.json(
        200,
        {
            "count": len(quotas),
            "quotas": {ship: quota.as_dict() for ship, quota in quotas.items()},
        },
    )


def quota_set(runtime, request: Request) -> Response:
    payload = request.json_object()
    ship = require_text(payload, "ship")
    limit = require_number(payload, "limit")
    used = optional_number(payload, "used", 0.0)
    runtime.quotas.set(Quota(ship=ship, limit=limit, used=used))
    return Response.json(
        200,
        {"set": True, "ship": ship, "remaining": remaining(runtime.quotas, ship)},
    )


def quota_reserve(runtime, request: Request) -> Response:
    payload = request.json_object()
    ship = require_text(payload, "ship")
    demand = require_number(payload, "demand")
    reserved = reserve(runtime.quotas, ship, demand)
    return Response.json(
        200,
        {"reserved": reserved, "remaining": remaining(runtime.quotas, ship)},
    )


def quota_release(runtime, request: Request) -> Response:
    payload = request.json_object()
    ship = require_text(payload, "ship")
    amount = require_number(payload, "amount")
    released = release(runtime.quotas, ship, amount)
    return Response.json(
        200,
        {"released": released, "remaining": remaining(runtime.quotas, ship)},
    )

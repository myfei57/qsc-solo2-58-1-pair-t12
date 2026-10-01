"""Berth reservation endpoints."""

from __future__ import annotations

from portpower.berth.schedule import Reservation
from portpower.console.http import BadRequest, Request, Response
from portpower.console.validation import require_text


def reservation_book(runtime, request: Request) -> Response:
    payload = request.json_object()
    try:
        reservation = Reservation(
            berth=require_text(payload, "berth"),
            ship=require_text(payload, "ship"),
            start=require_text(payload, "start"),
            end=require_text(payload, "end"),
        )
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    runtime.scheduler.book(reservation)
    return Response.json(
        200,
        {"booked": True, "reservation": reservation.as_dict()},
    )


def reservation_list(runtime, request: Request) -> Response:
    code = request.query_one("berth")
    if code:
        reservation = runtime.scheduler.get(code)
        return Response.json(
            200,
            {
                "found": reservation is not None,
                "reservation": reservation.as_dict() if reservation else None,
            },
        )
    reservations = runtime.scheduler.list_all()
    return Response.json(
        200,
        {"count": len(reservations), "reservations": [r.as_dict() for r in reservations]},
    )


def reservation_cancel(runtime, request: Request) -> Response:
    code = request.query_one("berth", "") or ""
    runtime.scheduler.cancel(code)
    return Response.json(
        200,
        {"cancelled": True, "remaining": runtime.scheduler.count()},
    )

"""Cable inventory and thermal monitoring endpoints."""

from __future__ import annotations

from portpower.cable.rating import classify
from portpower.console.http import BadRequest, Request, Response
from portpower.console.validation import require_number, valid_temperature
from portpower.disconn.trip import trip_breaker


def cables(runtime, request: Request) -> Response:
    identifiers = runtime.cables.identifiers()
    selected = runtime.cables.select(runtime.cable.rated_temperature)
    detail = {}
    for identifier in identifiers:
        cable = runtime.cables.get(identifier)
        if cable is not None:
            detail[identifier] = cable.describe()
    return Response.json(
        200,
        {
            "count": runtime.cables.count(),
            "ids": identifiers,
            "ratings": runtime.cables.ratings(),
            "detail": detail,
            "selected": selected.identifier if selected is not None else None,
        },
    )


def cable_monitor(runtime, request: Request) -> Response:
    temperature = runtime.sensor.read()
    return Response.json(
        200,
        {
            "monitor": runtime.monitor.summary(),
            "filter_average": runtime.filter.average,
            "protection": {
                "threshold": runtime.protector.threshold,
                "tripped": runtime.protector.tripped,
                "breaches": runtime.protector.breaches,
            },
            "temperature": temperature,
            "rating": classify(temperature, runtime.cable.rated_temperature).value,
        },
    )


def cable_sample(runtime, request: Request) -> Response:
    payload = request.json_object()
    temperature = require_number(payload, "temperature")
    if not valid_temperature(temperature):
        raise BadRequest("invalid temperature")
    runtime.sensor.set(temperature)
    runtime.monitor.observe(temperature)
    breach = runtime.protector.verdict(runtime.sensor.read())
    if breach:
        trip_breaker(runtime.shore)
    return Response.json(
        200,
        {
            "temperature": temperature,
            "filtered": runtime.filter.average,
            "rating": classify(temperature, runtime.cable.rated_temperature).value,
            "breach": breach,
            "breaker_state": runtime.shore.state.value,
        },
    )

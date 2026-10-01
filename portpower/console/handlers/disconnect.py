"""Disconnect endpoint."""

from __future__ import annotations

from portpower.console.flows.disconnect import DisconnectRequest, run_disconnect
from portpower.console.http import Request, Response


def disconnect(runtime, request: Request) -> Response:
    payload = request.json_object()
    result = run_disconnect(runtime, DisconnectRequest.from_payload(payload))
    return Response.json(200, result.as_dict())

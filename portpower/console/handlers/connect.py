"""Connect endpoint."""

from __future__ import annotations

from portpower.console.flows.connect import ConnectRequest, run_connect
from portpower.console.http import Request, Response


def connect(runtime, request: Request) -> Response:
    payload = request.json_object()
    result = run_connect(runtime, ConnectRequest.from_payload(payload))
    return Response.json(200, result.as_dict())

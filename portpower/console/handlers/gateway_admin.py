"""Operator endpoints for version windows, legacy usage and write limits."""

from __future__ import annotations

from datetime import datetime, timezone

from portpower.console.gateway.windows import TransitionWindow, parse_instant
from portpower.console.http import BadRequest, Request, Response
from portpower.console.validation import require_text


def version_list(runtime, request: Request) -> Response:
    now = datetime.now(timezone.utc)
    windows = runtime.windows.describe(now)
    paths = {}
    for path, info in runtime.contracts.describe().items():
        entry = dict(info)
        for version_info in entry["versions"].values():
            version_info["window"] = None
        for version, window in windows.get(path, {}).items():
            if version in entry["versions"]:
                entry["versions"][version]["window"] = window
        paths[path] = entry
    return Response.json(200, {"paths": paths})


def window_set(runtime, request: Request) -> Response:
    payload = request.json_object()
    path = require_text(payload, "path")
    version = require_text(payload, "version")
    deprecated_raw = require_text(payload, "deprecated_at")
    sunset_raw = require_text(payload, "sunset_at")
    contract = runtime.contracts.for_path(path)
    if contract is None:
        raise BadRequest(f"no version contract for path {path!r}")
    if version == contract.current:
        raise BadRequest(f"{version!r} is the current version for {path}")
    if contract.shape(version) is None:
        raise BadRequest(f"unknown version {version!r} for {path}")
    try:
        window = TransitionWindow(
            path=path,
            version=version,
            deprecated_at=parse_instant(deprecated_raw),
            sunset_at=parse_instant(sunset_raw),
        )
        runtime.windows.set(window)
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    return Response.json(
        200, {"set": True, "window": window.as_dict(datetime.now(timezone.utc))}
    )


def window_clear(runtime, request: Request) -> Response:
    payload = request.json_object()
    path = require_text(payload, "path")
    version = require_text(payload, "version")
    cleared = runtime.windows.clear(path, version)
    return Response.json(200, {"cleared": cleared, "path": path, "version": version})


def version_usage(runtime, request: Request) -> Response:
    path = request.query_one("path")
    return Response.json(200, {"paths": runtime.version_usage.report(path)})


def ratelimit_status(runtime, request: Request) -> Response:
    return Response.json(200, runtime.rate_limiter.snapshot())


def ratelimit_configure(runtime, request: Request) -> Response:
    payload = request.json_object()
    capacity = _optional_number(payload, "capacity")
    refill = _optional_number(payload, "refill_per_second")
    enabled = payload.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        raise BadRequest("enabled must be a boolean")
    try:
        config = runtime.rate_limiter.configure(
            capacity=capacity,
            refill_per_second=refill,
            enabled=enabled,
        )
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    return Response.json(200, {"set": True, "config": config.as_dict()})


def _optional_number(payload: dict[str, object], key: str) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BadRequest(f"{key} must be a number")
    return float(value)

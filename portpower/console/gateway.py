"""Request pipeline in front of the route table.

Every request passes through, in order:

1. version negotiation and the per-path transition window,
2. legacy-to-canonical request adaptation,
3. idempotent-replay lookup (cached answers cost nothing),
4. the write-rate limiter (reads and detected replays are exempt),
5. the handler, then canonical-to-legacy response adaptation.

The gateway only needs ``dispatch`` from the router, so it stays a drop-in
for anything that used to talk to the router directly.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime, time as day_time, timezone
from email.utils import format_datetime
from math import ceil
from typing import Any

from portpower.config import Settings
from portpower.console.http import BadRequest, Request, Response
from portpower.console.ratelimit import (
    CachedResponse,
    Decision,
    IdempotencyMismatch,
    IdempotencyStore,
    RateLimiter,
)
from portpower.console.router import Router
from portpower.console.usage import VersionUsage
from portpower.console.versioning import (
    UnknownVersion,
    VersionWindow,
    adapt_request_payload,
    adapt_response_payload,
    load_windows,
    negotiate_version,
)
from portpower.store.usage import UsageLog

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CLIENT_HEADER = "x-client-id"
IDEMPOTENCY_HEADER = "idempotency-key"

# Detects writes that are guaranteed no-ops because they were applied
# before; such replays never consume rate-limit tokens.
ReplayDetector = Callable[[Request], bool]


class Gateway:
    def __init__(
        self,
        router: Router,
        *,
        windows: dict[str, VersionWindow],
        limiter: RateLimiter | None = None,
        idempotency: IdempotencyStore | None = None,
        usage: VersionUsage | None = None,
        replay_detectors: dict[str, ReplayDetector] | None = None,
        today: Callable[[], date] | None = None,
    ) -> None:
        self._router = router
        self._windows = dict(windows)
        self._limiter = limiter
        self._idempotency = idempotency
        self._usage = usage
        self._replay_detectors = dict(replay_detectors or {})
        self._today = today or date.today

    def dispatch(self, request: Request) -> Response:
        method = request.method.upper()
        handler = self._router.resolve(method, request.path)
        if handler is None:
            return self._router.dispatch(request)

        window = self._windows.get(request.path)
        version: str | None = None
        if window is not None:
            try:
                version = negotiate_version(request, window)
            except UnknownVersion as exc:
                return Response.json(
                    400,
                    {
                        "error": f"unknown API version {exc.version!r}",
                        "path": window.path,
                        "supported": list(exc.supported),
                    },
                )
            rejection = self._window_rejection(window, version)
            if rejection is not None:
                return rejection
            if self._usage is not None:
                self._usage.record(client_key(request), request.path, version)
            if version == window.legacy:
                request = _adapt_request(request, window)

        client = client_key(request)
        is_write = method in WRITE_METHODS
        idem_key = request.headers.get(IDEMPOTENCY_HEADER, "").strip() if is_write else ""
        fingerprint = ""
        if idem_key and self._idempotency is not None:
            fingerprint = _fingerprint(request, version)
            try:
                cached = self._idempotency.lookup(client, idem_key, fingerprint)
            except IdempotencyMismatch:
                return Response.json(
                    409,
                    {"error": "idempotency key was already used with a different request"},
                )
            if cached is not None:
                return Response(
                    status=cached.status,
                    payload=cached.payload,
                    content_type=cached.content_type,
                    headers={"Idempotency-Replayed": "true"},
                )

        if is_write and self._limiter is not None and not self._is_replay(request):
            decision = self._limiter.check(client)
            if not decision.allowed:
                return _rate_limited(decision)

        response = handler(request)

        if window is not None and version == window.legacy:
            response = _adapt_response(response, window)
        if idem_key and self._idempotency is not None and response.status < 500:
            self._idempotency.store(
                client,
                idem_key,
                fingerprint,
                CachedResponse(response.status, response.payload, response.content_type),
            )
        if window is not None and version is not None:
            response = _with_version_headers(response, window, version)
        return response

    def describe_policy(self) -> dict[str, Any]:
        today = self._today()
        windows: list[dict[str, Any]] = []
        for path in sorted(self._windows):
            window = self._windows[path]
            entry: dict[str, Any] = {
                "path": path,
                "legacy": window.legacy,
                "current": window.current,
                "default": window.default,
                "legacy_start": _iso(window.legacy_start),
                "legacy_end": _iso(window.legacy_end),
                "legacy_active": window.legacy_active(today),
                "fields": {
                    "canonical_to_legacy": dict(window.fields),
                    "legacy_to_canonical": {
                        legacy: canonical
                        for canonical, legacy in window.fields.items()
                    },
                },
            }
            if window.legacy_end is not None:
                entry["days_remaining"] = (window.legacy_end - today).days
            windows.append(entry)
        return {"today": today.isoformat(), "windows": windows}

    def describe_usage(self) -> dict[str, Any]:
        legacy_by_path = {
            path: window.legacy for path, window in self._windows.items()
        }
        if self._usage is None:
            return {
                "clients": {},
                "legacy": {"client_count": 0, "total_requests": 0, "clients": {}},
            }
        return self._usage.report(legacy_by_path)

    def _window_rejection(self, window: VersionWindow, version: str) -> Response | None:
        if version != window.legacy:
            return None
        today = self._today()
        if window.legacy_start is not None and today < window.legacy_start:
            return Response.json(
                400,
                {
                    "error": (
                        f"version {version!r} for {window.path} is not accepted "
                        f"before {window.legacy_start.isoformat()}"
                    ),
                    "supported": list(window.versions),
                },
            )
        if window.legacy_end is not None and today > window.legacy_end:
            return Response.json(
                410,
                {
                    "error": (
                        f"version {version!r} for {window.path} was retired on "
                        f"{window.legacy_end.isoformat()}"
                    ),
                    "sunset": window.legacy_end.isoformat(),
                    "supported": [window.current],
                },
            )
        return None

    def _is_replay(self, request: Request) -> bool:
        detector = self._replay_detectors.get(request.path)
        return detector is not None and detector(request)


def build_gateway(runtime, router: Router, settings: Settings) -> Gateway:
    """Wire the gateway with its management endpoints onto the router."""

    gateway = Gateway(
        router,
        windows=load_windows(settings.version_policy, settings.data_dir),
        limiter=RateLimiter(
            client_capacity=settings.rate_capacity,
            client_refill=settings.rate_refill,
            global_capacity=settings.rate_global_capacity,
            global_refill=settings.rate_global_refill,
        ),
        idempotency=IdempotencyStore(ttl_seconds=settings.idempotency_ttl),
        usage=VersionUsage(runtime.store),
        replay_detectors={"/meter": _meter_replay_detector(runtime)},
    )
    register_management_routes(router, gateway)
    return gateway


def register_management_routes(router: Router, gateway: Gateway) -> None:
    """Expose the version policy and the legacy-usage report."""

    router.get(
        "/version/policy",
        lambda request: Response.json(200, gateway.describe_policy()),
    )
    router.get(
        "/version/usage",
        lambda request: Response.json(200, gateway.describe_usage()),
    )


def client_key(request: Request) -> str:
    explicit = request.headers.get(CLIENT_HEADER, "").strip()
    if explicit:
        return explicit
    if request.client:
        return request.client
    return "anonymous"


def _meter_replay_detector(runtime) -> ReplayDetector:
    """A reading whose timestamp is already logged is a no-op resend."""

    def is_replay(request: Request) -> bool:
        try:
            payload = request.json_object()
        except BadRequest:
            return False
        timestamp = payload.get("timestamp")
        if not isinstance(timestamp, str) or not timestamp.strip():
            return False
        return timestamp.strip() in UsageLog(runtime.store).timestamps()

    return is_replay


def _adapt_request(request: Request, window: VersionWindow) -> Request:
    if not request.body:
        return request
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return request  # the handler reports the malformed body
    if not isinstance(payload, dict):
        return request
    adapted = adapt_request_payload(payload, window.legacy, window)
    return replace(
        request, body=json.dumps(adapted, ensure_ascii=False).encode("utf-8")
    )


def _adapt_response(response: Response, window: VersionWindow) -> Response:
    if not 200 <= response.status < 300:
        return response
    if not response.content_type.startswith("application/json"):
        return response
    try:
        payload = json.loads(response.payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return response
    if not isinstance(payload, dict):
        return response
    adapted = adapt_response_payload(payload, window)
    return Response(
        status=response.status,
        payload=json.dumps(adapted, ensure_ascii=False).encode("utf-8"),
        content_type=response.content_type,
        headers=response.headers,
    )


def _with_version_headers(
    response: Response, window: VersionWindow, version: str
) -> Response:
    headers = dict(response.headers)
    headers["X-API-Version"] = version
    if version == window.legacy:
        if window.legacy_end is not None:
            sunset = datetime.combine(
                window.legacy_end, day_time(23, 59, 59), tzinfo=timezone.utc
            )
            headers["Deprecation"] = f"@{int(sunset.timestamp())}"
            headers["Sunset"] = format_datetime(sunset, usegmt=True)
        else:
            headers["Deprecation"] = "true"
    return replace(response, headers=headers)


def _rate_limited(decision: Decision) -> Response:
    retry_after = max(1, ceil(decision.retry_after))
    return Response(
        status=429,
        payload=json.dumps(
            {
                "error": "rate limit exceeded",
                "scope": decision.scope,
                "retry_after_seconds": retry_after,
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={"Retry-After": str(retry_after)},
    )


def _fingerprint(request: Request, version: str | None) -> str:
    digest = hashlib.sha256()
    digest.update(request.method.upper().encode("utf-8"))
    digest.update(b"\n")
    digest.update(request.path.encode("utf-8"))
    digest.update(b"\n")
    digest.update((version or "").encode("utf-8"))
    digest.update(b"\n")
    digest.update(request.body)
    return digest.hexdigest()


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None

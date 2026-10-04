"""The gateway: versioning, write throttling and idempotent replay in one pipeline.

Pipeline order for every request:

1. Idempotent replay — a known ``Idempotency-Key`` returns its stored
   response immediately, without touching version checks, the limiter
   or the handler.
2. Version negotiation — explicit declarations win, conflicts are 400,
   retired versions are 410; the body is rewritten to canonical fields.
3. Write throttling — only write methods and only requests that will
   actually dispatch consume a token.
4. Dispatch, then the response is rewritten for the negotiated version
   and stamped with version/deprecation headers; legacy traffic is
   recorded for the usage report.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import format_datetime

from portpower.console.errors import error_response
from portpower.console.gateway.contracts import ContractRegistry
from portpower.console.gateway.idempotency import MAX_KEY_LENGTH, IdempotencyCache
from portpower.console.gateway.negotiate import (
    Negotiation,
    adapt_request,
    adapt_response,
    negotiate,
)
from portpower.console.gateway.ratelimit import RateLimiter
from portpower.console.gateway.usage import VersionUsageLog
from portpower.console.gateway.windows import (
    DEPRECATED,
    GONE,
    TransitionWindow,
    WindowRegistry,
)
from portpower.console.http import BadRequest, Request, Response
from portpower.console.router import Router

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
IDEMPOTENCY_HEADER = "idempotency-key"
CLIENT_HEADERS = ("x-client-id", "x-api-key")
MAX_CLIENT_LENGTH = 128


def client_identity(request: Request) -> str:
    """Best-effort caller identity: explicit header, then remote address."""

    for name in CLIENT_HEADERS:
        value = request.headers.get(name)
        if value and value.strip():
            return value.strip()[:MAX_CLIENT_LENGTH]
    if request.remote:
        return request.remote
    return "anonymous"


class Gateway:
    """Sits in front of the router and keeps the version/throttle promises."""

    def __init__(
        self,
        router: Router,
        contracts: ContractRegistry,
        windows: WindowRegistry,
        usage: VersionUsageLog,
        limiter: RateLimiter,
        idempotency: IdempotencyCache,
    ) -> None:
        self._router = router
        self._contracts = contracts
        self._windows = windows
        self._usage = usage
        self._limiter = limiter
        self._idempotency = idempotency

    @classmethod
    def from_runtime(cls, router: Router, runtime) -> "Gateway":
        return cls(
            router,
            runtime.contracts,
            runtime.windows,
            runtime.version_usage,
            runtime.rate_limiter,
            runtime.idempotency,
        )

    def dispatch(self, request: Request) -> Response:
        if request.method.upper() in WRITE_METHODS:
            raw_key = request.headers.get(IDEMPOTENCY_HEADER)
            if raw_key is not None:
                key = raw_key.strip()
                if not key or len(key) > MAX_KEY_LENGTH:
                    return Response.json(
                        400, {"error": f"invalid {IDEMPOTENCY_HEADER} header"}
                    )
                return self._replayable(request, key)
        return self._execute(request)

    def describe(self) -> list[str]:
        return self._router.describe()

    def __len__(self) -> int:
        return len(self._router)

    def _replayable(self, request: Request, key: str) -> Response:
        client = client_identity(request)
        with self._idempotency.lock_for(client, key):
            cached = self._idempotency.lookup(client, key)
            if cached is not None:
                return cached.to_response(key)
            response = self._execute(request)
            if 200 <= response.status < 300:
                self._idempotency.store(client, key, response)
            return response

    def _execute(self, request: Request) -> Response:
        contract = self._contracts.for_path(request.path)
        if contract is None:
            return self._throttle(request)
        try:
            negotiation = negotiate(contract, request)
            adapted = adapt_request(negotiation, request)
        except BadRequest as exc:
            return error_response(exc)
        now = datetime.now(timezone.utc)
        window = self._windows.for_path_version(request.path, negotiation.version)
        if window is not None and window.status(now) == GONE:
            self._record_usage(request, negotiation)
            return _gone_response(negotiation, window)
        response = self._throttle(adapted)
        response = adapt_response(negotiation, response)
        response = _with_version_headers(response, negotiation, window, now)
        if not negotiation.is_current:
            self._record_usage(request, negotiation)
        return response

    def _throttle(self, request: Request) -> Response:
        if request.method.upper() not in WRITE_METHODS:
            return self._router.dispatch(request)
        allowed, retry_after = self._limiter.allow(client_identity(request))
        if not allowed:
            return _too_many_requests(retry_after, self._limiter.config().capacity)
        return self._router.dispatch(request)

    def _record_usage(self, request: Request, negotiation: Negotiation) -> None:
        self._usage.record(
            request.path, negotiation.version, client_identity(request)
        )


def _gone_response(negotiation: Negotiation, window: TransitionWindow) -> Response:
    return Response.json(
        410,
        {
            "error": (
                f"version {negotiation.version} of {negotiation.contract.path} "
                f"was retired at {window.sunset_at.isoformat()}"
            ),
            "version": negotiation.version,
            "current_version": negotiation.contract.current,
            "sunset_at": window.sunset_at.isoformat(),
        },
    )


def _too_many_requests(retry_after: float, capacity: float) -> Response:
    return Response(
        status=429,
        payload=json.dumps(
            {
                "error": "write rate limit exceeded",
                "retry_after_seconds": round(retry_after, 3),
                "write_limit": capacity,
                "hint": (
                    "retry after the indicated delay; resends carrying a "
                    "stable Idempotency-Key are never limited"
                ),
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
    )


def _with_version_headers(
    response: Response,
    negotiation: Negotiation,
    window: TransitionWindow | None,
    now: datetime,
) -> Response:
    headers = dict(response.headers)
    headers["X-Api-Version"] = negotiation.version
    headers["X-Api-Current-Version"] = negotiation.contract.current
    if window is not None and window.status(now) == DEPRECATED:
        headers["Deprecation"] = "true"
        headers["Sunset"] = format_datetime(window.sunset_at, usegmt=True)
        headers["Link"] = '</versions>; rel="deprecation"'
    return replace(response, headers=headers)

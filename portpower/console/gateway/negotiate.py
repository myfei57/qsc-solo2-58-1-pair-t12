"""Version negotiation: explicit declarations win, nothing is guessed.

A version may be declared in the ``X-Api-Version`` header, the
``version`` query parameter or the ``version`` body field. Two different
declarations are a 400, not a coin flip. Without a declaration the
payload shape is sniffed; a field supplied under two names is a conflict
that only an explicit version may resolve.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

from portpower.console.gateway.contracts import PathContract, VersionShape
from portpower.console.http import BadRequest, Request, Response

VERSION_HEADER = "x-api-version"
VERSION_QUERY = "version"
VERSION_BODY_FIELD = "version"


@dataclass(frozen=True)
class Negotiation:
    """The outcome of negotiating one request against a contract."""

    contract: PathContract
    version: str
    explicit: bool

    @property
    def is_current(self) -> bool:
        return self.version == self.contract.current


def negotiate(contract: PathContract, request: Request) -> Negotiation:
    declared = _declared_versions(request)
    if len(declared) > 1:
        raise BadRequest(
            "conflicting version declarations: " + ", ".join(sorted(declared))
        )
    if declared:
        version = next(iter(declared))
        if contract.shape(version) is None:
            raise BadRequest(
                f"unknown version {version!r} for {request.path}; "
                f"supported: {', '.join(contract.versions)}"
            )
        return Negotiation(contract, version, explicit=True)
    return Negotiation(contract, _sniff(contract, request), explicit=False)


def adapt_request(negotiation: Negotiation, request: Request) -> Request:
    """Rewrite the body into canonical field names for the handler."""

    payload = request.json_object()
    if not isinstance(payload, dict):
        return request  # let the handler raise its own "must be an object"
    shape = negotiation.contract.shape(negotiation.version)
    if shape is None:
        return request
    translated = _translate(negotiation.contract, shape, payload, negotiation.explicit)
    had_version_field = VERSION_BODY_FIELD in translated
    translated.pop(VERSION_BODY_FIELD, None)
    if translated == payload and not had_version_field:
        return request
    body = json.dumps(translated, ensure_ascii=False).encode("utf-8")
    return replace(request, body=body)


def adapt_response(negotiation: Negotiation, response: Response) -> Response:
    """Rewrite a success body back into the shape the client speaks."""

    if negotiation.is_current or not 200 <= response.status < 300:
        return response
    shape = negotiation.contract.shape(negotiation.version)
    if shape is None or (not shape.response_fields and not shape.response_drop):
        return response
    try:
        body = json.loads(response.payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return response
    if not isinstance(body, dict):
        return response
    for canonical, local in shape.response_fields.items():
        if canonical in body:
            body[local] = body.pop(canonical)
    for key in shape.response_drop:
        body.pop(key, None)
    return replace(
        response,
        payload=json.dumps(body, ensure_ascii=False).encode("utf-8"),
    )


def _declared_versions(request: Request) -> set[str]:
    declared: set[str] = set()
    header = request.headers.get(VERSION_HEADER)
    if header and header.strip():
        declared.add(header.strip())
    query = request.query_one(VERSION_QUERY)
    if query and query.strip():
        declared.add(query.strip())
    payload = request.json_object()
    if isinstance(payload, dict):
        body_version = payload.get(VERSION_BODY_FIELD)
        if isinstance(body_version, str) and body_version.strip():
            declared.add(body_version.strip())
    return declared


def _sniff(contract: PathContract, request: Request) -> str:
    payload = request.json_object()
    if not isinstance(payload, dict):
        return contract.current
    matched = {
        version
        for version in contract.legacy_versions
        if _uses_shape(contract.shape(version), payload)
    }
    if len(matched) > 1:
        raise BadRequest(
            f"payload matches multiple versions of {contract.path}; "
            f"declare one explicitly via {VERSION_HEADER}"
        )
    if matched:
        return next(iter(matched))
    return contract.current


def _uses_shape(shape: VersionShape | None, payload: dict[str, Any]) -> bool:
    if shape is None:
        return False
    return any(
        local != canonical and local in payload
        for local, canonical in shape.request_fields.items()
    )


def _translate(
    contract: PathContract,
    shape: VersionShape,
    payload: dict[str, Any],
    explicit: bool,
) -> dict[str, Any]:
    """Rename every known version-local field to its canonical name.

    Canonicalization uses the union of all shapes' renames, so any known
    name is understood regardless of the negotiated version. A field
    supplied under two different names is a conflict: without an explicit
    version we refuse to guess; with one, the name belonging to the
    declared version wins (for the current version, the canonical name).
    """

    renames: dict[str, str] = {}
    for name in contract.legacy_versions:
        legacy = contract.shape(name)
        if legacy is not None:
            renames.update(legacy.request_fields)
    if not renames:
        return dict(payload)
    translated: dict[str, Any] = {}
    sources: dict[str, str] = {}
    for key, value in payload.items():
        canonical = renames.get(key, key)
        existing = sources.get(canonical)
        if existing is not None and existing != key:
            if not explicit:
                raise BadRequest(
                    f"fields {existing!r} and {key!r} both map to {canonical!r}; "
                    f"declare {VERSION_HEADER} to disambiguate"
                )
            preferred = _preferred_name(shape, canonical)
            if key != preferred and existing != preferred:
                raise BadRequest(
                    f"fields {existing!r} and {key!r} both map to {canonical!r} "
                    f"but neither belongs to version {shape.name!r}"
                )
            if key != preferred:
                continue  # the declared version's own name was already seen
        sources[canonical] = key
        translated[canonical] = value
    return translated


def _preferred_name(shape: VersionShape, canonical: str) -> str:
    for local, target in shape.request_fields.items():
        if target == canonical:
            return local
    return canonical

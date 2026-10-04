"""Per-path API version windows and payload field adaptation.

Handlers speak one canonical (current) version of each body.  During a
transition window the same path also accepts the legacy shape: the gateway
renames legacy fields onto their canonical names before the handler runs
and renames them back on the way out, so old clients keep parsing
responses exactly as before.

Version selection is deterministic.  An explicit indicator (the
``X-API-Version`` header or the ``version`` query parameter) always wins;
without one the path's configured default applies.  When both an old and a
new field are present, the field belonging to the negotiated version takes
precedence.  The version is never inferred from which fields are present.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from portpower.console.http import Request

DEFAULT_LEGACY = "v1"
DEFAULT_CURRENT = "v2"
POLICY_FILE_NAME = "version_policy.json"

# Canonical (current) field name -> legacy field name, per path.
DEFAULT_FIELD_MAPS: dict[str, dict[str, str]] = {
    "/connect": {"ship_id": "ship", "max_load": "load"},
    "/meter": {"kwh": "value"},
    "/quota": {"ship_id": "ship"},
    "/quota/reserve": {"ship_id": "ship"},
    "/quota/release": {"ship_id": "ship"},
}


class UnknownVersion(ValueError):
    """Raised when a request asks for a version the path does not serve."""

    def __init__(self, version: str, supported: tuple[str, ...]) -> None:
        super().__init__(f"unknown API version {version!r}")
        self.version = version
        self.supported = supported


@dataclass(frozen=True)
class VersionWindow:
    """Transition window during which one path accepts two versions."""

    path: str
    legacy: str = DEFAULT_LEGACY
    current: str = DEFAULT_CURRENT
    legacy_start: date | None = None
    legacy_end: date | None = None
    default: str = DEFAULT_LEGACY
    fields: Mapping[str, str] = field(default_factory=dict)

    @property
    def versions(self) -> tuple[str, ...]:
        seen: list[str] = []
        for version in (self.legacy, self.current):
            if version not in seen:
                seen.append(version)
        return tuple(seen)

    def legacy_active(self, today: date) -> bool:
        if self.legacy_start is not None and today < self.legacy_start:
            return False
        if self.legacy_end is not None and today > self.legacy_end:
            return False
        return True

    def validate(self) -> None:
        if self.legacy == self.current:
            raise ValueError(f"{self.path}: legacy and current versions must differ")
        if self.default not in self.versions:
            raise ValueError(
                f"{self.path}: default version {self.default!r} is not supported"
            )
        if (
            self.legacy_start is not None
            and self.legacy_end is not None
            and self.legacy_start > self.legacy_end
        ):
            raise ValueError(f"{self.path}: legacy window starts after it ends")


def negotiate_version(request: "Request", window: VersionWindow) -> str:
    """Pick the request's version: explicit indicator first, else the default."""

    explicit = (
        request.headers.get("x-api-version") or request.query_one("version") or ""
    ).strip()
    if not explicit:
        return window.default
    if explicit not in window.versions:
        raise UnknownVersion(explicit, window.versions)
    return explicit


def adapt_request_payload(
    payload: dict[str, Any], version: str, window: VersionWindow
) -> dict[str, Any]:
    """Rewrite a body onto canonical field names.

    On conflict the negotiated version's field wins; a lone field of the
    other version is still accepted and normalised.
    """

    out = dict(payload)
    for canonical, legacy in window.fields.items():
        has_canonical = canonical in out
        has_legacy = legacy in out
        if version == window.legacy:
            if has_legacy:
                out[canonical] = out.pop(legacy)
        elif has_canonical:
            out.pop(legacy, None)
        elif has_legacy:
            out[canonical] = out.pop(legacy)
    return out


def adapt_response_payload(
    payload: dict[str, Any], window: VersionWindow
) -> dict[str, Any]:
    """Rename canonical response fields back to their legacy names."""

    out = dict(payload)
    for canonical, legacy in window.fields.items():
        if canonical in out:
            out[legacy] = out.pop(canonical)
    return out


def default_windows() -> dict[str, VersionWindow]:
    return {
        path: VersionWindow(path=path, fields=dict(fields))
        for path, fields in DEFAULT_FIELD_MAPS.items()
    }


def load_windows(policy_path: str, fallback_dir: str) -> dict[str, VersionWindow]:
    """Load per-path windows, falling back to the built-in defaults.

    ``policy_path`` points at a JSON document; when empty, a
    ``version_policy.json`` inside ``fallback_dir`` is honoured if present.
    File entries replace the default window for their path.
    """

    path = _resolve_policy_path(policy_path, fallback_dir)
    if path is None:
        return default_windows()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    entries = document.get("windows") if isinstance(document, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"{path}: expected an object with a 'windows' list")
    windows = default_windows()
    for entry in entries:
        window = _window_from_entry(entry, path)
        windows[window.path] = window
    return windows


def _resolve_policy_path(policy_path: str, fallback_dir: str) -> Path | None:
    if policy_path.strip():
        path = Path(policy_path.strip())
        if not path.is_file():
            raise ValueError(f"version policy file not found: {path}")
        return path
    fallback = Path(fallback_dir) / POLICY_FILE_NAME
    return fallback if fallback.is_file() else None


def _window_from_entry(entry: Any, source: Path) -> VersionWindow:
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        raise ValueError(f"{source}: every window needs a 'path' string")
    path = entry["path"].strip()
    fields = entry.get("fields")
    if fields is None:
        fields = dict(DEFAULT_FIELD_MAPS.get(path, {}))
    if not isinstance(fields, dict):
        raise ValueError(f"{source}: 'fields' for {path} must be an object")
    window = VersionWindow(
        path=path,
        legacy=str(entry.get("legacy", DEFAULT_LEGACY)),
        current=str(entry.get("current", DEFAULT_CURRENT)),
        legacy_start=_parse_date(entry.get("legacy_start"), source, path),
        legacy_end=_parse_date(entry.get("legacy_end"), source, path),
        default=str(entry.get("default", DEFAULT_LEGACY)),
        fields={str(k): str(v) for k, v in fields.items()},
    )
    window.validate()
    return window


def _parse_date(raw: Any, source: Path, path: str) -> date | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{source}: dates for {path} must be ISO strings")
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"{source}: invalid date {raw!r} for {path}, expected YYYY-MM-DD"
        ) from exc

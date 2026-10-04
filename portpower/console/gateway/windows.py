"""Per-path transition windows: when a legacy version starts and stops being served.

Windows are operator configuration, not code, so they live in the record
store and survive restarts. A version without a window is simply served
indefinitely; a window moves it from ``stable`` to ``deprecated`` (still
served, with warning headers) to ``gone`` (rejected with 410).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from portpower.store.kvstore import RecordStore

STORE_KEY = "console.version-windows"

STABLE = "stable"
DEPRECATED = "deprecated"
GONE = "gone"


def parse_instant(text: str) -> datetime:
    """Parse an ISO-8601 instant; naive values are read as UTC."""

    value = text.strip()
    if not value:
        raise ValueError("timestamp is empty")
    if value.endswith(("Z", "z")):
        value = value[:-1] + "+00:00"
    try:
        instant = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {text!r}") from exc
    if instant.tzinfo is None:
        return instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc)


@dataclass(frozen=True)
class TransitionWindow:
    path: str
    version: str
    deprecated_at: datetime
    sunset_at: datetime

    def status(self, now: datetime) -> str:
        if now < self.deprecated_at:
            return STABLE
        if now < self.sunset_at:
            return DEPRECATED
        return GONE

    def as_dict(self, now: datetime) -> dict[str, Any]:
        return {
            "path": self.path,
            "version": self.version,
            "deprecated_at": self.deprecated_at.isoformat(),
            "sunset_at": self.sunset_at.isoformat(),
            "status": self.status(now),
        }


def _window_from_entry(
    path: str, version: str, entry: Any
) -> TransitionWindow | None:
    if not isinstance(entry, dict):
        return None
    try:
        return TransitionWindow(
            path=path,
            version=version,
            deprecated_at=parse_instant(str(entry["deprecated_at"])),
            sunset_at=parse_instant(str(entry["sunset_at"])),
        )
    except (KeyError, ValueError):
        return None


class WindowRegistry:
    """Durable record of the transition window for each path/version."""

    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def for_path_version(self, path: str, version: str) -> TransitionWindow | None:
        entry = self._load().get(path, {}).get(version)
        if entry is None:
            return None
        return _window_from_entry(path, version, entry)

    def for_path(self, path: str) -> dict[str, TransitionWindow]:
        windows: dict[str, TransitionWindow] = {}
        for version, entry in self._load().get(path, {}).items():
            window = _window_from_entry(path, version, entry)
            if window is not None:
                windows[version] = window
        return windows

    def set(self, window: TransitionWindow) -> None:
        if window.deprecated_at >= window.sunset_at:
            raise ValueError("deprecated_at must be before sunset_at")

        def mutate(doc: Any) -> tuple[Any, None]:
            doc = doc if isinstance(doc, dict) else {}
            doc.setdefault(window.path, {})[window.version] = {
                "deprecated_at": window.deprecated_at.isoformat(),
                "sunset_at": window.sunset_at.isoformat(),
            }
            return doc, None

        self._store.update_json(STORE_KEY, mutate)

    def clear(self, path: str, version: str) -> bool:
        def mutate(doc: Any) -> tuple[Any, bool]:
            doc = doc if isinstance(doc, dict) else {}
            versions = doc.get(path)
            existed = isinstance(versions, dict) and version in versions
            if isinstance(versions, dict):
                versions.pop(version, None)
                if not versions:
                    doc.pop(path, None)
            return doc, existed

        return bool(self._store.update_json(STORE_KEY, mutate))

    def describe(self, now: datetime) -> dict[str, dict[str, Any]]:
        return {
            path: {
                version: window.as_dict(now)
                for version, window in self.for_path(path).items()
            }
            for path in sorted(self._load())
        }

    def _load(self) -> dict[str, Any]:
        doc = self._store.get_json(STORE_KEY)
        return doc if isinstance(doc, dict) else {}

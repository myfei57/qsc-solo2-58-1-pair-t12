"""Records which client talks to which path on which API version.

The record is persisted through the document store so the picture of
remaining legacy clients survives restarts; that picture is what tells
operators when a transition window can be closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from portpower.store.kvstore import RecordStore

USAGE_KEY = "console.version-usage"


class VersionUsage:
    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def record(self, client: str, path: str, version: str) -> None:
        now = _timestamp()

        def mutate(document: Any) -> tuple[Any, None]:
            doc = document if isinstance(document, dict) else {}
            clients = doc.setdefault("clients", {})
            entry = clients.setdefault(client, {})
            paths = entry.setdefault("paths", {})
            versions = paths.setdefault(path, {})
            stat = versions.setdefault(version, {"count": 0, "first_seen": now})
            stat["count"] = int(stat.get("count", 0)) + 1
            stat["last_seen"] = now
            return doc, None

        self._store.update_json(USAGE_KEY, mutate)

    def report(self, legacy_by_path: Mapping[str, str]) -> dict[str, Any]:
        """Full per-client breakdown plus a summary of legacy-only users."""

        document = self._store.get_json(USAGE_KEY)
        clients = document.get("clients", {}) if isinstance(document, dict) else {}
        legacy_clients: dict[str, Any] = {}
        total_legacy = 0
        for client, entry in clients.items():
            paths = entry.get("paths", {}) if isinstance(entry, dict) else {}
            client_count = 0
            client_paths: dict[str, str] = {}
            last_seen = ""
            for path, versions in paths.items():
                legacy = legacy_by_path.get(path)
                if legacy is None or not isinstance(versions, dict):
                    continue
                stat = versions.get(legacy)
                if not isinstance(stat, dict):
                    continue
                count = int(stat.get("count", 0))
                if count <= 0:
                    continue
                client_count += count
                client_paths[path] = legacy
                last_seen = max(last_seen, str(stat.get("last_seen", "")))
            if client_count:
                legacy_clients[client] = {
                    "count": client_count,
                    "last_seen": last_seen,
                    "paths": client_paths,
                }
                total_legacy += client_count
        return {
            "generated_at": _timestamp(),
            "clients": clients,
            "legacy": {
                "client_count": len(legacy_clients),
                "total_requests": total_legacy,
                "clients": legacy_clients,
            },
        }


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

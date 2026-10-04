"""Who is still talking to legacy versions, and when they last did."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from portpower.store.kvstore import RecordStore

STORE_KEY = "console.version-usage"


class VersionUsageLog:
    """Durable per-client counters for legacy version traffic."""

    def __init__(
        self,
        store: RecordStore,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def record(self, path: str, version: str, client: str) -> None:
        seen = self._clock().isoformat()

        def mutate(doc: Any) -> tuple[Any, None]:
            doc = doc if isinstance(doc, dict) else {}
            versions = doc.setdefault(path, {})
            clients = versions.setdefault(version, {}).setdefault("clients", {})
            entry = clients.setdefault(client, {"count": 0, "first_seen": seen})
            entry["count"] = int(entry.get("count", 0)) + 1
            entry["last_seen"] = seen
            return doc, None

        self._store.update_json(STORE_KEY, mutate)

    def report(self, path: str | None = None) -> dict[str, Any]:
        doc = self._store.get_json(STORE_KEY)
        doc = doc if isinstance(doc, dict) else {}
        if path is not None:
            doc = {path: doc.get(path, {})}
        return {
            one_path: {
                version: {
                    "total": sum(
                        int(client.get("count", 0))
                        for client in data.get("clients", {}).values()
                        if isinstance(client, dict)
                    ),
                    "clients": data.get("clients", {}),
                }
                for version, data in sorted(versions.items())
                if isinstance(data, dict)
            }
            for one_path, versions in sorted(doc.items())
            if isinstance(versions, dict)
        }

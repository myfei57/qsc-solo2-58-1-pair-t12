"""Read-only quota projections used by the quota endpoints."""

from __future__ import annotations

from portpower.quota.manager import QuotaManager


def remaining(manager: QuotaManager, ship: str) -> float:
    quota = manager.get(ship)
    return quota.remaining if quota is not None else 0.0

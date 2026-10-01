"""Quota reservation and release operations."""

from __future__ import annotations

from portpower.quota.manager import QuotaManager
from portpower.quota.quota import Quota


def reserve(manager: QuotaManager, ship: str, demand: float) -> bool:
    quota = manager.get(ship)
    if quota is None or demand < 0:
        return False
    if quota.used + demand > quota.limit:
        return False
    manager.set(quota.with_usage(demand))
    return True


def release(manager: QuotaManager, ship: str, amount: float) -> bool:
    quota = manager.get(ship)
    if quota is None or amount < 0:
        return False
    remaining_used = max(0.0, quota.used - amount)
    manager.set(Quota(ship=quota.ship, limit=quota.limit, used=remaining_used))
    return True

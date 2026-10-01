"""Higher level berth operations shared by the HTTP flows."""

from __future__ import annotations

from portpower.berth.registry import BerthRegistry
from portpower.ns.catalog import Catalog


def allocate(registry: BerthRegistry, catalog: Catalog, ship_id: str) -> str | None:
    """Assign ``ship_id`` to the first catalog berth that is still free."""

    def is_available(code: str) -> bool:
        berth = registry.get(code)
        return berth is not None and not berth.occupied

    code = catalog.first_available(is_available)
    if code is None:
        return None
    berth = registry.get(code)
    if berth is None:
        return None
    berth.assign(ship_id)
    return code


def vacate(registry: BerthRegistry, code: str) -> bool:
    return registry.release(code)


def occupant(registry: BerthRegistry, code: str) -> str | None:
    return registry.ship_at(code)

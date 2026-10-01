"""Durable freeze flag that blocks further readings for a berth."""

from __future__ import annotations

from portpower.meter.meter import Meter, freeze_key


def freeze(meter: Meter) -> bool:
    meter.mark_frozen()
    store = meter.store
    if store is not None:
        store.put_json(freeze_key(meter.berth), True)
    return meter.frozen


def unfreeze(meter: Meter) -> bool:
    meter.clear_frozen()
    store = meter.store
    if store is not None:
        store.delete(freeze_key(meter.berth))
    return not meter.frozen


def is_frozen(meter: Meter) -> bool:
    return meter.frozen

"""Health, status and snapshot endpoints."""

from __future__ import annotations

from portpower.cable.rating import classify
from portpower.console.http import Request, Response
from portpower.store.query import count_with_prefix
from portpower.store.snapshot import export_snapshot, import_snapshot
from portpower.store.stats import key_count, largest_key, total_bytes


def health(runtime, request: Request) -> Response:
    return Response.json(
        200,
        {
            "identity": runtime.harbor.identity(),
            "region": runtime.harbor.region,
        },
    )


def status(runtime, request: Request) -> Response:
    temperature = runtime.sensor.read()
    rating = classify(temperature, runtime.cable.rated_temperature)
    return Response.json(
        200,
        {
            "harbor": runtime.harbor.identity(),
            "breaker": runtime.shore.describe(),
            "breaker_conducts": runtime.shore.state.conducts,
            "frequency": runtime.syncer.current,
            "frequency_within": runtime.syncer.within(),
            "frequency_stable": runtime.syncer.stable(),
            "temperature": temperature,
            "filter_average": runtime.filter.average,
            "cable": runtime.cable.describe(),
            "cable_rating": rating.value,
            "cable_alarm": rating.is_alarm,
            "protection": {
                "threshold": runtime.protector.threshold,
                "tripped": runtime.protector.tripped,
                "breaches": runtime.protector.breaches,
            },
            "monitor": runtime.monitor.summary(),
            "audit_count": runtime.ledger.count(),
            "berths_occupied": runtime.berths.occupied_count(),
            "fleet_count": runtime.fleet.count(),
            "cable_count": runtime.cables.count(),
            "phase_current": runtime.phase.current.value,
            "phase_history": [item.value for item in runtime.phase.history()],
            "phase_reversed": runtime.phase.reversed,
            "phase_flips": runtime.phase.flips(),
            "store_keys": key_count(runtime.store),
            "store_bytes": total_bytes(runtime.store),
            "store_largest_key": largest_key(runtime.store),
            "meter_records": count_with_prefix(runtime.store, "meter.usage"),
            "quota_ships": sorted(runtime.quotas.all()),
            "berth_catalog": runtime.catalog.codes(),
            "catalog_count": runtime.catalog.count(),
        },
    )


def snapshot(runtime, request: Request) -> Response:
    return Response.json(200, export_snapshot(runtime.store))


def restore(runtime, request: Request) -> Response:
    payload = request.json_object()
    restored = import_snapshot(runtime.store, payload)
    return Response.json(200, {"restored": True, "keys": restored})

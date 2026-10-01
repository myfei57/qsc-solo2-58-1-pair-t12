"""Route table that binds the handlers to the runtime."""

from __future__ import annotations

from functools import partial

from portpower.console.handlers import (
    audit,
    berth,
    breaker,
    cable,
    connect,
    disconnect,
    frequency,
    meter,
    quota,
    schedule,
    ship,
    system,
)
from portpower.console.http import Request, Response
from portpower.console.router import Router


def build_router(runtime) -> Router:
    router = Router()
    bind = partial

    router.get("/health", bind(system.health, runtime))
    router.get("/status", bind(system.status, runtime))
    router.post("/snapshot", bind(system.snapshot, runtime))
    router.post("/restore", bind(system.restore, runtime))

    router.get("/freq", bind(frequency.freq_get, runtime))
    router.post("/freq", bind(frequency.freq_set, runtime))
    router.get("/freq/samples", bind(frequency.freq_samples, runtime))

    router.post("/connect", bind(connect.connect, runtime))
    router.post("/disconnect", bind(disconnect.disconnect, runtime))

    router.post("/meter", bind(meter.record_reading, runtime))
    router.get("/usage", bind(meter.usage, runtime))
    router.get("/billing", bind(meter.billing, runtime))
    router.get("/meter/period", bind(meter.period, runtime))
    router.post("/meter/freeze", bind(meter.freeze_meter, runtime))
    router.post("/meter/unfreeze", bind(meter.unfreeze_meter, runtime))

    router.get("/berths", bind(berth.berths, runtime))
    router.get("/berth/status", bind(berth.berth_status, runtime))
    router.get("/berth", bind(berth.berth_detail, runtime))
    router.post("/berth/allocate", bind(berth.allocate, runtime))
    router.post("/berth/vacate", bind(berth.release_berth, runtime))

    router.get("/ships", bind(ship.ships, runtime))
    router.get("/ship", bind(ship.ship_detail, runtime))
    router.post("/retrofit", bind(ship.retrofit, runtime))
    router.get("/ship/history", bind(ship.history, runtime))

    router.get("/audit", bind(audit.audit_list, runtime))
    router.get("/audit/latest", bind(audit.audit_latest, runtime))
    router.get("/audit/summary", bind(audit.audit_summary, runtime))
    router.get("/audit/tail", bind(audit.audit_tail, runtime))

    router.get("/quota", bind(quota.quota_list, runtime))
    router.post("/quota", bind(quota.quota_set, runtime))
    router.post("/quota/reserve", bind(quota.quota_reserve, runtime))
    router.post("/quota/release", bind(quota.quota_release, runtime))

    router.get("/breaker", bind(breaker.breaker_state, runtime))
    router.post("/breaker/trip", bind(breaker.breaker_trip, runtime))
    router.post("/breaker/reset", bind(breaker.breaker_reset, runtime))
    router.get("/breaker/interlock", bind(breaker.breaker_interlock, runtime))

    router.post("/reservation", bind(schedule.reservation_book, runtime))
    router.get("/reservations", bind(schedule.reservation_list, runtime))
    router.delete("/reservation", bind(schedule.reservation_cancel, runtime))

    router.get("/cables", bind(cable.cables, runtime))
    router.get("/cable/monitor", bind(cable.cable_monitor, runtime))
    router.post("/cable/sample", bind(cable.cable_sample, runtime))

    def route_table(request: Request) -> Response:
        return Response.json(200, {"count": len(router), "routes": router.describe()})

    router.get("/routes", route_table)
    return router

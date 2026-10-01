"""Translation of domain exceptions into HTTP responses."""

from __future__ import annotations

from portpower.berth.berth import BerthOccupied, BerthVacant
from portpower.berth.registry import NoBerthAvailable
from portpower.berth.schedule import ReservationConflict
from portpower.console.http import BadRequest, Response
from portpower.disconn.breaker import BreakerNotClosed
from portpower.disconn.close import ArmMissing
from portpower.disconn.limit import LoadExceedsProfile
from portpower.disconn.parallel import FrequencyOutOfSync
from portpower.disconn.trip import BreakerAlreadyClosed
from portpower.meter.binder import BindingMissing
from portpower.meter.meter import MeterFrozen
from portpower.phase.verifier import PhaseReversed
from portpower.plug.engage import NoMeterBinding
from portpower.plug.release import PlugNotEngaged
from portpower.store.kvstore import StoreKeyError

CONFLICT_ERRORS: tuple[type[Exception], ...] = (
    BerthOccupied,
    BerthVacant,
    ReservationConflict,
    NoBerthAvailable,
    BreakerNotClosed,
    BreakerAlreadyClosed,
    ArmMissing,
    FrequencyOutOfSync,
    BindingMissing,
    MeterFrozen,
    LoadExceedsProfile,
    PhaseReversed,
    NoMeterBinding,
    PlugNotEngaged,
    StoreKeyError,
)


def error_response(exc: Exception) -> Response:
    if isinstance(exc, LookupError) and not isinstance(exc, StoreKeyError):
        return Response.json(404, {"error": str(exc)})
    if isinstance(exc, CONFLICT_ERRORS):
        return Response.json(409, {"error": str(exc)})
    if isinstance(exc, (BadRequest, ValueError, TypeError)):
        return Response.json(400, {"error": str(exc)})
    return Response.json(500, {"error": str(exc)})

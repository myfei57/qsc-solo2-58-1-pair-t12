"""Composition root that wires every domain package together."""

from __future__ import annotations

from dataclasses import dataclass

from portpower.audit.ledger import Ledger
from portpower.berth.mapping import BerthMapping
from portpower.berth.registry import BerthRegistry
from portpower.berth.schedule import Scheduler
from portpower.cable.cable import Cable
from portpower.cable.filter import MovingAverageFilter
from portpower.cable.inventory import CableInventory
from portpower.cable.monitor import TemperatureMonitor
from portpower.cable.sensor import TemperatureSensor
from portpower.disconn.breaker import Breaker
from portpower.disconn.limit import LimitEnforcer
from portpower.disconn.protect import Protector
from portpower.freq.syncer import Syncer
from portpower.meter.binder import Binder
from portpower.meter.tariff import Tariff
from portpower.ns.catalog import Catalog
from portpower.ns.harbor import Harbor
from portpower.phase.state import PhaseState
from portpower.quota.manager import QuotaManager
from portpower.ship.fleet import Fleet
from portpower.ship.history import ProfileHistory
from portpower.ship.registry import ProfileRegistry
from portpower.store.kvstore import RecordStore

CATALOG_CODES: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1")
SHORE_CABLE = ("shore-1", 90.0)
PROTECTION_THRESHOLD = 90.0
FILTER_WINDOW = 3
MONITOR_WINDOW = 5
TARIFF_RATE = 0.95
SHORE_BREAKER_ID = "shore-main"


@dataclass
class Runtime:
    """All long-lived collaborators for one server process."""

    harbor: Harbor
    catalog: Catalog
    store: RecordStore
    ledger: Ledger
    quotas: QuotaManager
    profiles: ProfileRegistry
    fleet: Fleet
    mapping: BerthMapping
    berths: BerthRegistry
    binder: Binder
    syncer: Syncer
    sensor: TemperatureSensor
    filter: MovingAverageFilter
    cable: Cable
    cables: CableInventory
    tariff: Tariff
    monitor: TemperatureMonitor
    scheduler: Scheduler
    history: ProfileHistory
    phase: PhaseState
    shore: Breaker
    protector: Protector
    limiter: LimitEnforcer


def build_runtime(harbor: Harbor, store: RecordStore) -> Runtime:
    catalog = Catalog(CATALOG_CODES)
    berths = BerthRegistry()
    for code in catalog.codes():
        berths.add(code)

    filter_window = MovingAverageFilter(FILTER_WINDOW)
    cables = CableInventory()
    cable_id, cable_rating = SHORE_CABLE
    cables.add(cable_id, cable_rating)

    return Runtime(
        harbor=harbor,
        catalog=catalog,
        store=store,
        ledger=Ledger(store),
        quotas=QuotaManager(store),
        profiles=ProfileRegistry(store),
        fleet=Fleet(),
        mapping=BerthMapping(store),
        berths=berths,
        binder=Binder(store),
        syncer=Syncer(store),
        sensor=TemperatureSensor(),
        filter=filter_window,
        cable=cables.get(cable_id),
        cables=cables,
        tariff=Tariff(TARIFF_RATE),
        monitor=TemperatureMonitor(MONITOR_WINDOW),
        scheduler=Scheduler(store),
        history=ProfileHistory(store),
        phase=PhaseState(),
        shore=Breaker(SHORE_BREAKER_ID),
        protector=Protector(PROTECTION_THRESHOLD, filter_window),
        limiter=LimitEnforcer(ProfileRegistry(store)),
    )

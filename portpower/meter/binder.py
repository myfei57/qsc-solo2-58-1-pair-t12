"""Berth to vessel meter bindings, cached and persisted."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from portpower.store.kvstore import RecordStore

PREFIX = "meter.binding."
FINAL_PREFIX = "meter.final."


def binding_key(berth: str) -> str:
    return PREFIX + berth


def final_key(berth: str) -> str:
    return FINAL_PREFIX + berth


@dataclass(frozen=True)
class Binding:
    berth: str
    ship: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: object) -> "Binding | None":
        if not isinstance(payload, dict):
            return None
        berth = payload.get("berth")
        ship = payload.get("ship")
        if not isinstance(berth, str) or not isinstance(ship, str):
            return None
        if not berth or not ship:
            return None
        return cls(berth=berth, ship=ship)


class BindingMissing(RuntimeError):
    """Raised when a berth has no active meter binding."""


class Binder:
    def __init__(self, store: RecordStore) -> None:
        self._store = store
        self._current: dict[str, Binding] = {}

    def bind(self, binding: Binding) -> None:
        self._store.put_json(binding_key(binding.berth), binding.as_dict())
        self._current[binding.berth] = binding

    def load(self, berth: str) -> Binding | None:
        return Binding.from_dict(self._store.get_json(binding_key(berth)))

    def current(self, berth: str) -> Binding | None:
        return self._current.get(berth)

    def unbind(self, berth: str) -> None:
        self._store.delete(binding_key(berth))
        self._current.pop(berth, None)

    def record_final(self, berth: str, value: float) -> float:
        if self.load(berth) is None:
            raise BindingMissing(f"binding missing for berth {berth}")
        self._store.put_json(final_key(berth), float(value))
        return float(value)

    def final_value(self, berth: str) -> float | None:
        value = self._store.get_json(final_key(berth))
        if isinstance(value, (int, float)):
            return float(value)
        return None

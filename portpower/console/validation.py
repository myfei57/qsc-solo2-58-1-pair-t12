"""Request field validation shared by the connect and disconnect flows."""

from __future__ import annotations

from portpower.console.http import BadRequest
from portpower.ns.catalog import MAX_CODE_LENGTH

MIN_SHIP_ID_LENGTH = 2
MAX_SHIP_ID_LENGTH = 32
MIN_FREQUENCY = 45.0
MAX_FREQUENCY = 65.0
MIN_TEMPERATURE = -40.0
MAX_TEMPERATURE = 200.0


def normalize(value: str) -> str:
    return value.strip()


def valid_berth_code(value: str) -> bool:
    code = normalize(value)
    return bool(code) and len(code) <= MAX_CODE_LENGTH


def valid_ship_id(value: str) -> bool:
    ship = normalize(value)
    return MIN_SHIP_ID_LENGTH <= len(ship) <= MAX_SHIP_ID_LENGTH


def valid_frequency(value: float) -> bool:
    return MIN_FREQUENCY <= value <= MAX_FREQUENCY


def valid_load(value: float) -> bool:
    return value > 0


def valid_temperature(value: float) -> bool:
    return MIN_TEMPERATURE <= value <= MAX_TEMPERATURE


def require_text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BadRequest(f"{key} is required")
    return value.strip()


def require_number(payload: dict[str, object], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BadRequest(f"{key} must be a number")
    return float(value)


def optional_number(payload: dict[str, object], key: str, default: float) -> float:
    if key not in payload or payload[key] is None:
        return default
    return require_number(payload, key)


def optional_text(payload: dict[str, object], key: str, default: str = "") -> str:
    value = payload.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise BadRequest(f"{key} must be a string")
    return value.strip()

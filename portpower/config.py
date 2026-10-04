"""Runtime settings resolved from the process environment."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_DATA_DIR = "data"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
DEFAULT_RATE_CAPACITY = 20.0
DEFAULT_RATE_REFILL = 5.0
DEFAULT_RATE_GLOBAL_CAPACITY = 200.0
DEFAULT_RATE_GLOBAL_REFILL = 50.0
DEFAULT_IDEMPOTENCY_TTL = 86400.0


@dataclass(frozen=True)
class Settings:
    """Immutable view of the knobs that drive a single process."""

    data_dir: str
    host: str
    port: int
    version_policy: str = ""
    rate_capacity: float = DEFAULT_RATE_CAPACITY
    rate_refill: float = DEFAULT_RATE_REFILL
    rate_global_capacity: float = DEFAULT_RATE_GLOBAL_CAPACITY
    rate_global_refill: float = DEFAULT_RATE_GLOBAL_REFILL
    idempotency_ttl: float = DEFAULT_IDEMPOTENCY_TTL


def parse_listen_address(raw: str) -> tuple[str, int]:
    """Split a ``host:port`` string, an ``:port`` string, or a bare port."""

    text = raw.strip()
    if not text:
        raise ValueError("listen address is empty")
    if text.isdigit():
        return DEFAULT_HOST, _coerce_port(text)
    if ":" not in text:
        return text, DEFAULT_PORT
    host, _, port_text = text.rpartition(":")
    host = host.strip() or DEFAULT_HOST
    return host, _coerce_port(port_text)


def _coerce_port(text: str) -> int:
    try:
        port = int(text)
    except ValueError as exc:
        raise ValueError(f"invalid port: {text!r}") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"port out of range: {port}")
    return port


def _coerce_float(text: str, default: float, name: str) -> float:
    raw = text.strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"invalid {name}: {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive: {value}")
    return value


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Read ``PORTPOWER_*`` variables, falling back to local defaults."""

    env = os.environ if environ is None else environ
    data_dir = env.get("PORTPOWER_DATA_DIR", "").strip() or DEFAULT_DATA_DIR
    address = env.get("PORTPOWER_ADDR", "").strip()
    if address:
        host, port = parse_listen_address(address)
    else:
        host, port = DEFAULT_HOST, DEFAULT_PORT
    return Settings(
        data_dir=data_dir,
        host=host,
        port=port,
        version_policy=env.get("PORTPOWER_VERSION_POLICY", "").strip(),
        rate_capacity=_coerce_float(
            env.get("PORTPOWER_RATE_CAPACITY", ""), DEFAULT_RATE_CAPACITY, "rate capacity"
        ),
        rate_refill=_coerce_float(
            env.get("PORTPOWER_RATE_REFILL", ""), DEFAULT_RATE_REFILL, "rate refill"
        ),
        rate_global_capacity=_coerce_float(
            env.get("PORTPOWER_RATE_GLOBAL_CAPACITY", ""),
            DEFAULT_RATE_GLOBAL_CAPACITY,
            "global rate capacity",
        ),
        rate_global_refill=_coerce_float(
            env.get("PORTPOWER_RATE_GLOBAL_REFILL", ""),
            DEFAULT_RATE_GLOBAL_REFILL,
            "global rate refill",
        ),
        idempotency_ttl=_coerce_float(
            env.get("PORTPOWER_IDEMPOTENCY_TTL", ""),
            DEFAULT_IDEMPOTENCY_TTL,
            "idempotency ttl",
        ),
    )

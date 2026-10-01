"""Identity of the control namespace a server instance owns."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Harbor:
    identifier: str
    name: str
    region: str = field(default="north")

    def __post_init__(self) -> None:
        if not self.identifier.strip():
            raise ValueError("harbor identifier is required")
        if not self.name.strip():
            raise ValueError("harbor name is required")

    def identity(self) -> str:
        """Stable string used by health checks and audit entries."""

        return f"{self.name}:{self.identifier}"

    def qualified(self, suffix: str) -> str:
        """Prefix a bare name with the namespace, e.g. ``north.berth.A1``."""

        cleaned = suffix.strip()
        if not cleaned:
            raise ValueError("suffix is required")
        return f"{self.region}.{cleaned}"

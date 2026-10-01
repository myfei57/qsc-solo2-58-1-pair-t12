"""One audit line."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AuditEntry:
    at: str
    event: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: object) -> "AuditEntry | None":
        if not isinstance(payload, dict):
            return None
        at = payload.get("at")
        event = payload.get("event")
        detail = payload.get("detail")
        if not all(isinstance(item, str) for item in (at, event, detail)):
            return None
        return cls(at=at, event=event, detail=detail)

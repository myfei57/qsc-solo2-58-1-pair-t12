"""Versioned field contracts: the API promise made for each path.

A contract declares which versions a path understands. The *current*
version is the canonical schema the handlers speak; every legacy shape
describes how its field names map onto the canonical ones and how the
canonical response maps back, so old clients keep working unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class VersionShape:
    """How one version of a path differs from the canonical schema.

    ``request_fields`` maps the version's own field names onto canonical
    names; ``response_fields`` maps canonical response keys back onto the
    names this version expects; ``response_drop`` lists canonical keys the
    version never had and must not see.
    """

    name: str
    request_fields: Mapping[str, str] = field(default_factory=dict)
    response_fields: Mapping[str, str] = field(default_factory=dict)
    response_drop: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PathContract:
    """Every version a path promises to understand."""

    path: str
    current: str
    shapes: Mapping[str, VersionShape]

    def shape(self, version: str) -> VersionShape | None:
        return self.shapes.get(version)

    @property
    def versions(self) -> tuple[str, ...]:
        return tuple(sorted(self.shapes))

    @property
    def legacy_versions(self) -> tuple[str, ...]:
        return tuple(name for name in self.versions if name != self.current)


def _contract(path: str, current: str, legacy: list[VersionShape]) -> PathContract:
    shapes: dict[str, VersionShape] = {current: VersionShape(name=current)}
    for shape in legacy:
        if shape.name == current:
            raise ValueError(f"legacy shape {shape.name!r} collides with current")
        shapes[shape.name] = shape
    return PathContract(path=path, current=current, shapes=shapes)


class ContractRegistry:
    """Lookup of the versioned contracts, keyed by path."""

    def __init__(self, contracts: list[PathContract]) -> None:
        self._contracts = {contract.path: contract for contract in contracts}

    def for_path(self, path: str) -> PathContract | None:
        return self._contracts.get(path)

    def paths(self) -> tuple[str, ...]:
        return tuple(sorted(self._contracts))

    def describe(self) -> dict[str, dict[str, object]]:
        return {
            path: {
                "current_version": contract.current,
                "versions": {
                    name: {
                        "request_fields": dict(shape.request_fields),
                        "response_fields": dict(shape.response_fields),
                        "response_drop": sorted(shape.response_drop),
                    }
                    for name, shape in sorted(contract.shapes.items())
                },
            }
            for path, contract in sorted(self._contracts.items())
        }


def default_contracts() -> ContractRegistry:
    """The promises currently made to console clients.

    The canonical (v2) schemas are what the handlers consume today. The
    v1 shapes keep the pre-rename field names alive for clients that
    cannot be upgraded in the field.
    """

    return ContractRegistry(
        [
            _contract(
                "/connect",
                current="v2",
                legacy=[
                    VersionShape(
                        name="v1",
                        request_fields={
                            "freq": "frequency",
                            "kw": "load",
                            "temp": "temperature",
                        },
                        response_fields={"breaker_state": "breaker"},
                        response_drop=frozenset({"headroom", "cable_rating"}),
                    )
                ],
            ),
            _contract(
                "/meter",
                current="v2",
                legacy=[
                    VersionShape(
                        name="v1",
                        request_fields={"ts": "timestamp", "reading": "value"},
                        response_drop=frozenset({"duplicate"}),
                    )
                ],
            ),
        ]
    )

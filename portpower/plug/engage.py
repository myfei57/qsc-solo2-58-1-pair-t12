"""Engagement of a plug requires an active meter binding for the berth."""

from __future__ import annotations

from portpower.plug.plug import Plug


class NoMeterBinding(RuntimeError):
    """Raised when the berth has no meter binding to anchor the plug to."""


def engage(plug: Plug, berth: str, binder) -> str:
    binding = binder.current(berth)
    if binding is None:
        raise NoMeterBinding(f"no meter binding for berth {berth}")
    plug.mark_engaged(binding.ship)
    return binding.ship

"""Releasing a plug returns it to the disconnected state."""

from __future__ import annotations

from portpower.plug.plug import Plug


class PlugNotEngaged(RuntimeError):
    """Raised when releasing a plug that was never engaged."""


def release(plug: Plug) -> None:
    if not plug.engaged:
        raise PlugNotEngaged(f"plug {plug.identifier} is not engaged")
    plug.mark_released()

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from src.engine.robot.tool_transform import compose_translation


class ToolRegistryClient(Protocol):
    def update_tool(
        self, tool_id: int, name: str | None, transform: Sequence[float], *,
        persist: bool, collision_profile: str | None = None,
    ) -> tuple[bool, str]: ...


class ToolActivator(Protocol):
    def set_active_tool(self, tool: int) -> bool: ...


class ToolActivationService:
    """Synchronize a resolved tool transform before selecting it on the robot."""

    def __init__(self, registry: ToolRegistryClient, activator: ToolActivator):
        self._registry = registry
        self._activator = activator

    def activate(
        self,
        *,
        tool_id: int,
        name: str,
        reference_transform: Sequence[float],
        relative_transform: Sequence[float],
        persist_registry: bool = True,
        collision_profile: str = "",
    ) -> tuple[bool, str, list[float]]:
        resolved = compose_translation(reference_transform, relative_transform)
        ok, message = self._registry.update_tool(
            int(tool_id), name, resolved, persist=bool(persist_registry),
            collision_profile=str(collision_profile or ""),
        )
        if not ok:
            return False, message or "Failed to synchronize tool transform", resolved
        if not self._activator.set_active_tool(int(tool_id)):
            return False, f"Tool {tool_id} was synchronized but could not be activated", resolved
        return True, f"Tool {tool_id} synchronized and activated", resolved

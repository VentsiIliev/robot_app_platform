from __future__ import annotations

from src.robot_systems.paint.processes.paint.destination import IWorkpieceDestination


class AutomaticDryerDestination(IWorkpieceDestination):
    """Adapt automatic-dryer coordination to the shared destination contract."""

    def __init__(self, coordinator) -> None:
        self._coordinator = coordinator

    def check_ready_for_release(self) -> tuple[bool, str]:
        return self._coordinator.wait_until_ready_for_release()

    def on_release_verified(self) -> bool:
        return bool(self._coordinator.on_workpiece_release_verified())

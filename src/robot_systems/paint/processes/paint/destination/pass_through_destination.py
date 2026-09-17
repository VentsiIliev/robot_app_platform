from __future__ import annotations

from .i_workpiece_destination import IWorkpieceDestination


class PassThroughWorkpieceDestination(IWorkpieceDestination):
    """Destination for cells that need no external handoff coordination."""

    def check_ready_for_release(self) -> tuple[bool, str]:
        return True, ""

    def on_release_verified(self) -> bool:
        return True

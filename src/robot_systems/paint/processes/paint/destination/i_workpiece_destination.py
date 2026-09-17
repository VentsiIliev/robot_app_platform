from __future__ import annotations

from abc import ABC, abstractmethod


class IWorkpieceDestination(ABC):
    """Machine-specific handoff performed around verified workpiece release."""

    @abstractmethod
    def check_ready_for_release(self) -> tuple[bool, str]:
        """Return whether the destination can accept the next workpiece."""

    @abstractmethod
    def on_release_verified(self) -> bool:
        """Handle a workpiece after the robot has verified its release."""

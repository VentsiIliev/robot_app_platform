from __future__ import annotations

from abc import ABC, abstractmethod

from src.engine.hardware.dryer.models.dryer_state import DryerState
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData


class IDryerController(ABC):
    """High-level dryer controller interface."""

    @abstractmethod
    def write_data(self, data: DryerWriteData) -> bool:
        """Write the full dryer command/configuration register block."""

    @abstractmethod
    def get_state(self) -> DryerState:
        """Read and decode the dryer status register."""

    @abstractmethod
    def move_servos(self, data: DryerWriteData | None = None) -> bool:
        """Start the servo movement command."""

    @abstractmethod
    def open_plate(self, data: DryerWriteData | None = None) -> bool:
        """Start the open-plate command."""

    @abstractmethod
    def close_plate(self, data: DryerWriteData | None = None) -> bool:
        """Start the close-plate command."""

    @abstractmethod
    def next_position(self, data: DryerWriteData | None = None) -> bool:
        """Start the move-to-next-position command."""

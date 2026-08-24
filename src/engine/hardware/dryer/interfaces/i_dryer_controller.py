from __future__ import annotations

from abc import ABC, abstractmethod

from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_state import DryerState
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData


class IDryerController(ABC):
    """High-level dryer controller interface."""

    @abstractmethod
    def initialize(self) -> bool:
        """Write the current defaults to the dryer and report success."""

    @abstractmethod
    def shutdown(self) -> None:
        """Release controller transport resources."""

    @abstractmethod
    def update_config(self, config: DryerConfig) -> None:
        """Replace the defaults used by subsequent dryer commands."""

    @abstractmethod
    def write_data(self, data: DryerWriteData) -> bool:
        """Write the full dryer command/configuration register block."""

    @abstractmethod
    def get_state(self) -> DryerState:
        """Read and decode the dryer status register."""

    @abstractmethod
    def home(self, data: DryerWriteData | None = None) -> bool:
        """Start the dryer homing command."""

    @abstractmethod
    def execute_command(self, command: int, data: DryerWriteData | None = None) -> bool:
        """Execute a configured numeric dryer command."""

    @abstractmethod
    def move_servos(self, data: DryerWriteData | None = None) -> bool:
        """Compatibility alias for eject()."""

    @abstractmethod
    def eject(self, data: DryerWriteData | None = None) -> bool:
        """Eject the loaded detail."""

    @abstractmethod
    def open_plate(self, data: DryerWriteData | None = None) -> bool:
        """Compatibility alias for close_plate()."""

    @abstractmethod
    def close_plate(self, data: DryerWriteData | None = None) -> bool:
        """Start the close-plate command."""

    @abstractmethod
    def next_position(self, data: DryerWriteData | None = None) -> bool:
        """Start the move-to-next-position command."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.robot_systems.glue.processes.glue_dispensing.dispensing_settings import (
    DispensingSegmentSettings,
)


class IDispenseChannelService(ABC):
    @abstractmethod
    def resolve_motor_address(self, glue_type: str | None) -> int:
        """Return motor address for the requested glue type, or -1 if unresolved."""

    @abstractmethod
    def start_dispense(
        self,
        glue_type: str | None,
        settings: DispensingSegmentSettings | None = None,
    ) -> tuple[bool, int | None]:
        """Start pump flow for the resolved dispense channel."""

    @abstractmethod
    def stop_dispense(
        self,
        glue_type: str | None,
        settings: DispensingSegmentSettings | None = None,
    ) -> tuple[bool, int | None]:
        """Stop pump flow for the resolved dispense channel."""

    @abstractmethod
    def get_last_exception(self) -> Exception | None:
        """Return the last low-level pump-control exception, if any."""

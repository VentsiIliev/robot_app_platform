from __future__ import annotations

from abc import abstractmethod

from src.engine.hardware.dryer.interfaces.i_dryer_controller import IDryerController
from src.engine.core.i_health_checkable import IHealthCheckable


class IDryerService(IDryerController, IHealthCheckable):
    """Stable lifecycle and command boundary for dryer hardware."""

    @abstractmethod
    def enable(self) -> bool:
        """Construct and initialize the configured dryer controller."""

    @abstractmethod
    def enable_async(self) -> bool:
        """Start controller construction and initialization without blocking."""

    @abstractmethod
    def disable(self) -> None:
        """Release dryer hardware resources and reject commands."""

    @abstractmethod
    def is_enabled(self) -> bool:
        """Return whether the dryer is enabled or currently initializing."""

    @abstractmethod
    def is_healthy(self) -> bool:
        """Return the cached dryer availability without performing I/O."""

    @property
    @abstractmethod
    def last_error(self) -> str | None:
        """Return the most recent lifecycle or command error."""

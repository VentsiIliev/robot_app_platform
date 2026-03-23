from __future__ import annotations

from abc import ABC, abstractmethod

from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard.dashboard_state import (
    DashboardState,
)


class IMyDashboardService(ABC):
    """Standard dashboard contract for a robot-system-specific process."""

    @abstractmethod
    def get_process_id(self) -> str: ...

    @abstractmethod
    def load_state(self) -> DashboardState: ...

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def pause(self) -> None: ...

    @abstractmethod
    def resume(self) -> None: ...

    @abstractmethod
    def reset_errors(self) -> None: ...

from __future__ import annotations

from abc import ABC, abstractmethod

from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardState


class IPaintDashboardService(ABC):

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


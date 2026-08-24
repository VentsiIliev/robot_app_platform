from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardState


@dataclass(frozen=True)
class ContourTransformDebugResult:
    success: bool
    message: str
    image_path: str | None = None


@dataclass(frozen=True)
class DashboardCommandResult:
    success: bool
    message: str
    device_id: str | None = None
    enabled: bool | None = None


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

    @abstractmethod
    def relieve_cable(self) -> DashboardCommandResult: ...

    @abstractmethod
    def get_auxiliary_states(self) -> dict[str, bool]: ...

    @abstractmethod
    def set_auxiliary_enabled(self, device_id: str, enabled: bool) -> DashboardCommandResult: ...

    @abstractmethod
    def capture_latest_contour_transform_debug(self) -> ContourTransformDebugResult: ...

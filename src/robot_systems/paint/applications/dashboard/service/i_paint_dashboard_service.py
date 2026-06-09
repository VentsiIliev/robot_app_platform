from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardState


@dataclass(frozen=True)
class ContourTransformDebugResult:
    success: bool
    message: str
    image_path: str | None = None


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
    def capture_latest_contour_transform_debug(self) -> ContourTransformDebugResult: ...

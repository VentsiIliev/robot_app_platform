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

    @abstractmethod
    def test_pickup(self) -> tuple[bool, str]: ...

    @abstractmethod
    def go_to_calibration(self) -> None: ...

    @abstractmethod
    def move_to_calibration_ptp(self) -> None: ...

    @abstractmethod
    def move_to_home_zeros(self) -> None: ...

    @abstractmethod
    def pickup_to_paint_position(self) -> tuple[bool, str]: ...

    @abstractmethod
    def test_pre_paint_marker_position(self) -> tuple[bool, str]: ...

    @abstractmethod
    def get_paint_marker_settings(self) -> dict: ...

    @abstractmethod
    def save_paint_marker_settings(self, settings: dict) -> tuple[bool, str]: ...

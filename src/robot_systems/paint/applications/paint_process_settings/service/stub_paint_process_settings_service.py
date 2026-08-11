from src.robot_systems.paint.applications.paint_process_settings.service.i_paint_process_settings_service import (
    IPaintProcessSettingsService,
)
from src.robot_systems.paint.processes.paint.config import PAINT_PROCESS_CONFIG, PaintProcessConfig


class StubPaintProcessSettingsService(IPaintProcessSettingsService):
    def __init__(
        self,
        initial_settings: PaintProcessConfig | None = None,
        dropoff_movement_group_configured: bool = True,
        current_position: list[float] | None = None,
    ):
        self._settings = initial_settings or PAINT_PROCESS_CONFIG
        self._dropoff_movement_group_configured = bool(dropoff_movement_group_configured)
        self._current_position = list(current_position or [0.0, 0.0, 200.0, 180.0, 0.0, 0.0])
        self.last_moved_waypoint: dict | None = None

    def load_settings(self) -> PaintProcessConfig:
        return self._settings

    def save_settings(self, settings: PaintProcessConfig) -> None:
        self._settings = settings
        print("Stub: Paint process settings saved")

    def is_dropoff_movement_group_configured(self) -> bool:
        return self._dropoff_movement_group_configured

    def dropoff_movement_group_configuration_error(self) -> str:
        if self._dropoff_movement_group_configured:
            return ""
        return "Dropoff movement group position, velocity, or acceleration is not configured."

    def get_current_robot_position(self) -> list[float] | None:
        return list(self._current_position)

    def move_to_waypoint(self, waypoint: dict) -> bool:
        self.last_moved_waypoint = dict(waypoint)
        print(f"Stub: Move to paint safe travel waypoint {waypoint}")
        return True

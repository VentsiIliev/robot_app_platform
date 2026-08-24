from src.applications.base.i_application_model import IApplicationModel
from src.robot_systems.paint.applications.paint_process_settings.service.i_paint_process_settings_service import (
    IPaintProcessSettingsService,
)
from src.robot_systems.paint.processes.paint.config import PaintProcessConfig


class PaintProcessSettingsModel(IApplicationModel):
    def __init__(self, service: IPaintProcessSettingsService):
        self._service = service
        self._settings: PaintProcessConfig | None = None

    def load(self) -> PaintProcessConfig:
        self._settings = self._service.load_settings()
        return self._settings

    def save(self, settings: PaintProcessConfig) -> None:
        self._service.save_settings(settings)
        self._settings = settings

    def is_dropoff_movement_group_configured(self) -> bool:
        return self._service.is_dropoff_movement_group_configured()

    def dropoff_movement_group_configuration_error(self) -> str:
        return self._service.dropoff_movement_group_configuration_error()

    def get_current_robot_position(self) -> list[float] | None:
        return self._service.get_current_robot_position()

    def move_to_waypoint(self, waypoint: dict) -> bool:
        return self._service.move_to_waypoint(waypoint)

    def get_pickup_safety_enabled(self) -> tuple[bool, bool]:
        return self._service.get_pickup_safety_enabled()

    @property
    def current_settings(self) -> PaintProcessConfig:
        if self._settings is None:
            self._settings = self._service.load_settings()
        return self._settings

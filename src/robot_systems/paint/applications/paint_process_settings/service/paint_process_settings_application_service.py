from typing import Callable

from src.robot_systems.paint.applications.paint_process_settings.service.i_paint_process_settings_service import (
    IPaintProcessSettingsService,
)
from src.robot_systems.paint.processes.paint.config import PaintProcessConfig
from src.robot_systems.paint.processes.paint.paint_process_config_service import (
    IPaintProcessConfigService,
)


class PaintProcessSettingsApplicationService(IPaintProcessSettingsService):
    def __init__(
        self,
        process_config_service: IPaintProcessConfigService,
        dropoff_group_provider: Callable[[], object | None] | None = None,
        current_position_provider: Callable[[], list[float] | None] | None = None,
    ):
        self._process_config_service = process_config_service
        self._dropoff_group_provider = dropoff_group_provider
        self._current_position_provider = current_position_provider

    def load_settings(self) -> PaintProcessConfig:
        return self._process_config_service.get_snapshot()

    def save_settings(self, settings: PaintProcessConfig) -> None:
        self._process_config_service.save(settings)

    def is_dropoff_movement_group_configured(self) -> bool:
        return self.dropoff_movement_group_configuration_error() == ""

    def dropoff_movement_group_configuration_error(self) -> str:
        if self._dropoff_group_provider is None:
            return "Dropoff movement group lookup is not available."
        try:
            group = self._dropoff_group_provider()
        except Exception:
            return "Could not read the Dropoff movement group from Robot Settings."
        if group is None:
            return "Dropoff movement group does not exist in Robot Settings."
        try:
            velocity = float(getattr(group, "velocity", 0) or 0)
        except (TypeError, ValueError):
            return "Dropoff movement group velocity is invalid."
        if velocity <= 0:
            return "Dropoff movement group velocity must be greater than 0 in Robot Settings."
        try:
            acceleration = float(getattr(group, "acceleration", 0) or 0)
        except (TypeError, ValueError):
            return "Dropoff movement group acceleration is invalid."
        if acceleration <= 0:
            return "Dropoff movement group acceleration must be greater than 0 in Robot Settings."
        try:
            position = group.parse_position()
        except Exception:
            return "Dropoff movement group position is invalid."
        if position is None or len(position) < 6:
            return "Dropoff movement group position is missing."
        try:
            [float(position[index]) for index in range(6)]
        except (TypeError, ValueError):
            return "Dropoff movement group position is invalid."
        return ""

    def get_current_robot_position(self) -> list[float] | None:
        if self._current_position_provider is None:
            return None
        try:
            position = self._current_position_provider()
        except Exception:
            return None
        if position is None:
            return None
        try:
            values = [float(value) for value in list(position)[:6]]
        except (TypeError, ValueError):
            return None
        return values if len(values) >= 6 else None

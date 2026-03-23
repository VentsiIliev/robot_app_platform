from __future__ import annotations

from src.engine.robot.height_measuring.height_correction_service import HeightCorrectionService
from src.engine.robot.targeting.robot_system_targeting_provider import RobotSystemTargetingProvider
from src.robot_systems.glue.settings_ids import SettingsID
from src.robot_systems.glue.targeting.point_names import CAMERA_POINT
from src.robot_systems.glue.targeting.frames import build_glue_target_frames
from src.robot_systems.glue.targeting.registry import build_glue_point_registry


class GlueRobotSystemTargetingProvider(RobotSystemTargetingProvider):
    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def _settings_service(self):
        return getattr(self._robot_system, "_settings_service", None)

    def _robot_config(self):
        return getattr(self._robot_system, "_robot_config", None)

    def _targeting_settings(self):
        settings_service = self._settings_service()
        if settings_service is not None:
            return settings_service.get(SettingsID.GLUE_TARGETING)
        return getattr(self._robot_system, "_glue_targeting", None)

    def build_point_registry(self):
        return build_glue_point_registry(self._targeting_settings())

    def build_frames(self):
        height_service = getattr(self._robot_system, "_height_measuring_service", None)
        height_correction = HeightCorrectionService(height_service) if height_service is not None else None
        return build_glue_target_frames(
            self._targeting_settings(),
            getattr(self._robot_system, "_navigation", None),
            height_correction,
        )

    def get_target_options(self) -> list[tuple[str, str]]:
        settings = self._targeting_settings()
        if settings is None:
            return []
        settings.ensure_defaults()
        return [(str(point.display_name or point.name), point.name) for point in settings.points]

    def get_default_target_name(self) -> str:
        return CAMERA_POINT

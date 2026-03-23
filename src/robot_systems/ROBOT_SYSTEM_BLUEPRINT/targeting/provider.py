from __future__ import annotations

from src.engine.robot.targeting.robot_system_targeting_provider import RobotSystemTargetingProvider
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.service_ids import ServiceID
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.settings_ids import SettingsID
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.targeting.point_names import CAMERA_POINT
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.targeting.frames import build_my_target_frames
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.targeting.registry import build_my_point_registry


class MyRobotSystemTargetingProvider(RobotSystemTargetingProvider):
    """TODO: Build targeting runtime objects for the concrete robot system."""

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_point_registry(self):
        settings = self._robot_system.get_settings(SettingsID.MY_TARGETING)
        return build_my_point_registry(settings)

    def build_frames(self):
        settings = self._robot_system.get_settings(SettingsID.MY_TARGETING)
        navigation = self._robot_system.get_optional_service(ServiceID.NAVIGATION)
        return build_my_target_frames(settings, navigation=navigation)

    def get_target_options(self) -> list[tuple[str, str]]:
        settings = self._robot_system.get_settings(self._robot_system.settings_id_targeting())
        settings.ensure_defaults()
        return [
            (str(point.display_name or point.name), point.name)
            for point in settings.points
        ]

    def get_default_target_name(self) -> str:
        return CAMERA_POINT

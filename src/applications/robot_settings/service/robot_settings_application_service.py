from enum import Enum
from typing import List, Optional, Tuple
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.applications.robot_settings.service.i_robot_settings_service import IRobotSettingsService
from src.engine.robot.features.navigation_service import NavigationService

class RobotSettingsApplicationService(IRobotSettingsService):

    def __init__(
        self,
        settings_service:  ISettingsService,
        config_key:        Enum,
        calibration_key:   Enum,
        robot_service:     Optional[IRobotService] = None,
        tool_settings_key: Optional[Enum]          = None,
        navigation_service: Optional[NavigationService] = None,
    ):
        self._settings          = settings_service
        self._config_key        = config_key
        self._calibration_key   = calibration_key
        self._robot             = robot_service
        self._tool_settings_key = tool_settings_key
        self._navigation = navigation_service

    def load_config(self) -> RobotSettings:
        return self._settings.get(self._config_key)

    def save_config(self, config: RobotSettings) -> None:
        self._settings.save(self._config_key, config)

    def load_calibration(self) -> RobotCalibrationSettings:
        return self._settings.get(self._calibration_key)

    def save_calibration(self, calibration: RobotCalibrationSettings) -> None:
        self._settings.save(self._calibration_key, calibration)

    def get_current_position(self) -> Optional[List[float]]:
        if self._robot is None:
            return None
        try:
            return self._robot.get_current_position()
        except Exception:
            return None

    def get_slot_info(self) -> List[Tuple[int, Optional[str]]]:
        """Returns (slot_id, tool_name) per slot. tool_name is None if slot is unassigned."""
        if self._tool_settings_key is None:
            return []
        try:
            tc = self._settings.get(self._tool_settings_key)
            if tc is None:
                return []
            tool_lookup = {t.id: t.name for t in tc.tools}
            return [
                (s.id, tool_lookup.get(s.tool_id) if s.tool_id is not None else None)
                for s in tc.slots
            ]
        except Exception:
            return []

    def move_to_group(self, group_name: str) -> bool:
        if self._navigation is None:
            return False
        try:
            return self._navigation.move_to_group(group_name)
        except Exception:
            return False

    def execute_group(self, group_name: str) -> bool:
        if self._navigation is None:
            return False
        try:
            return self._navigation.move_linear_group(group_name)
        except Exception:
            return False

    def move_to_point(self, group_name: str, point_str: str) -> bool:
        if self._navigation is None:
            return False
        try:
            values = [float(x.strip()) for x in point_str.strip("[] ").split(",")]
            if len(values) != 6:
                return False
            return self._navigation.move_to_position(values, group_name)
        except Exception:
            return False


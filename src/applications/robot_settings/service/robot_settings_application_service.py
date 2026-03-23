from enum import Enum
from typing import Callable, List, Optional, Tuple
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.applications.robot_settings.service.i_robot_settings_service import IRobotSettingsService
from src.engine.robot.features.navigation_service import NavigationService
from src.engine.robot.enums.axis import RobotAxis, Direction

class RobotSettingsApplicationService(IRobotSettingsService):

    def __init__(
        self,
        settings_service:  ISettingsService,
        config_key:        Enum,
        calibration_key:   Enum,
        robot_service:     Optional[IRobotService] = None,
        tool_settings_key: Optional[Enum]          = None,
        navigation_service: Optional[NavigationService] = None,
        load_targeting_definitions_fn: Optional[Callable[[], object]] = None,
        save_targeting_definitions_fn: Optional[Callable[[object], None]] = None,
    ):
        self._settings          = settings_service
        self._config_key        = config_key
        self._calibration_key   = calibration_key
        self._robot             = robot_service
        self._tool_settings_key = tool_settings_key
        self._navigation = navigation_service
        self._load_targeting_definitions_fn = load_targeting_definitions_fn
        self._save_targeting_definitions_fn = save_targeting_definitions_fn

    def load_config(self) -> RobotSettings:
        return self._settings.get(self._config_key)

    def save_config(self, config: RobotSettings) -> None:
        self._settings.save(self._config_key, config)

    def load_calibration(self) -> RobotCalibrationSettings:
        return self._settings.get(self._calibration_key)

    def save_calibration(self, calibration: RobotCalibrationSettings) -> None:
        self._settings.save(self._calibration_key, calibration)

    def load_targeting_definitions(self):
        if self._load_targeting_definitions_fn is None:
            return None
        return self._load_targeting_definitions_fn()

    def save_targeting_definitions(self, targeting) -> None:
        if self._save_targeting_definitions_fn is None:
            return
        self._save_targeting_definitions_fn(targeting)

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

    def move_to_group(self, group_name: str) -> tuple[bool, str]:
        if self._navigation is None:
            return False, "Navigation service not available"
        try:
            ok = self._navigation.move_to_group(group_name)
            if ok:
                return True, ""
            return False, (
                "Motion was blocked.\n"
                "The target position may be outside the configured safety limits.\n"
                "Open Settings → Safety tab to review and adjust the workspace bounds."
            )
        except Exception as e:
            return False, f"Motion error: {e}"

    def execute_group(self, group_name: str) -> tuple[bool, str]:
        if self._navigation is None:
            return False, "Navigation service not available"
        try:
            ok = self._navigation.move_linear_group(group_name)
            if ok:
                return True, ""
            return False, (
                "Execution was blocked.\n"
                "One or more trajectory positions may be outside the configured safety limits.\n"
                "Open Settings → Safety tab to review and adjust the workspace bounds."
            )
        except Exception as e:
            return False, f"Execution error: {e}"

    def move_to_point(self, group_name: str, point_str: str) -> tuple[bool, str]:
        if self._navigation is None:
            return False, "Navigation service not available"
        try:
            values = [float(x.strip()) for x in point_str.strip("[] ").split(",")]
            if len(values) != 6:
                return False, "Invalid position format — expected 6 values [x, y, z, rx_degrees, ry_degrees, rz_degrees]"
            ok = self._navigation.move_to_position(values, group_name)
            if ok:
                return True, ""
            return False, (
                "Motion was blocked.\n"
                "The target position may be outside the configured safety limits.\n"
                "Open Settings → Safety tab to review and adjust the workspace bounds."
            )
        except Exception as e:
            return False, f"Motion error: {e}"


    def jog(self, axis: str, direction: str, step: float) -> None:
        if self._robot is None:
            return
        try:
            self._robot.start_jog(
                RobotAxis.get_by_string(axis),
                Direction.get_by_string(direction),
                step,
            )
        except Exception:
            pass

    def stop_jog(self) -> None:
        if self._robot is None:
            return
        try:
            self._robot.stop_motion()
        except Exception:
            pass

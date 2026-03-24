import logging
from typing import Dict, Optional, List, Tuple

from src.engine.robot.configuration import (
    RobotSettings,
    RobotCalibrationSettings,
    MovementGroup,
    MovementGroupSettings,
)
from src.shared_contracts.declarations import MovementGroupDefinition
from src.applications.base.i_application_model import IApplicationModel
from src.applications.robot_settings.model.mapper import RobotCalibrationMapper, RobotSettingsMapper
from src.applications.robot_settings.service.i_robot_settings_service import IRobotSettingsService


class RobotSettingsModel(IApplicationModel):

    def __init__(self, service: IRobotSettingsService):
        self._service     = service
        self._config:      Optional[RobotSettings]            = None
        self._calibration: Optional[RobotCalibrationSettings] = None
        self._movement_groups: Optional[MovementGroupSettings] = None
        self._targeting_definitions: Optional[dict]           = None
        self._logger       = logging.getLogger(self.__class__.__name__)

    def load(self) -> tuple[RobotSettings, RobotCalibrationSettings, dict | None]:
        self._config      = self._service.load_config()
        self._calibration = self._service.load_calibration()
        self._movement_groups = self._service.load_movement_groups()
        self._targeting_definitions = self._service.load_targeting_definitions()
        return self._config, self._calibration, self._targeting_definitions

    def save(self, flat: dict, movement_groups: Dict[str, MovementGroup] = None, targeting_data: dict | None = None) -> None:
        movement_groups = movement_groups or {}
        updated = RobotSettingsMapper.from_flat_dict(flat, self._config)
        self._service.save_config(updated)
        self._config = updated
        self._logger.debug("Robot config saved")

        self._service.save_movement_groups(movement_groups)
        self._movement_groups = MovementGroupSettings(movement_groups=dict(movement_groups))
        self._logger.debug("Movement groups saved")

        updated_calib = RobotCalibrationMapper.from_flat_dict(flat, self._calibration)
        self._service.save_calibration(updated_calib)
        self._calibration = updated_calib
        self._logger.debug("Robot calibration saved")

        if targeting_data is not None:
            self._service.save_targeting_definitions(targeting_data)
            self._targeting_definitions = targeting_data
            self._logger.debug("Targeting definitions saved")

    def get_current_position(self) -> Optional[List[float]]:
        return self._service.get_current_position()

    def get_slot_info(self) -> List[Tuple[int, str]]:
        return self._service.get_slot_info()

    def get_movement_group_definitions(self) -> List[MovementGroupDefinition]:
        return self._service.get_movement_group_definitions()

    def get_expected_movement_groups(self) -> Dict[str, MovementGroup]:
        """Saved groups merged with declared movement-group defaults."""
        existing = dict(self._movement_groups.movement_groups) if self._movement_groups else {}
        for definition in self._service.get_movement_group_definitions():
            existing.setdefault(definition.id, definition.build_default_group())
        return existing

    def move_to_group(self, group_name: str) -> tuple[bool, str]:
        return self._service.move_to_group(group_name)

    def execute_group(self, group_name: str) -> tuple[bool, str]:
        return self._service.execute_group(group_name)

    def move_to_point(self, group_name: str, point_str: str) -> tuple[bool, str]:
        return self._service.move_to_point(group_name, point_str)

    def jog(self, axis: str, direction: str, step: float) -> None:
        self._service.jog(axis, direction, step)

    def stop_jog(self) -> None:
        self._service.stop_jog()

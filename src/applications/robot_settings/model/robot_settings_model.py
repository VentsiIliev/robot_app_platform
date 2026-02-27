import logging
from typing import Dict, Optional

from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings, MovementGroup
from src.applications.base.i_application_model import IApplicationModel
from src.applications.robot_settings.model.mapper import RobotCalibrationMapper, RobotSettingsMapper
from src.applications.robot_settings.service.i_robot_settings_service import IRobotSettingsService


class RobotSettingsModel(IApplicationModel):

    def __init__(self, service: IRobotSettingsService):
        self._service     = service
        self._config:      Optional[RobotSettings]            = None
        self._calibration: Optional[RobotCalibrationSettings] = None
        self._logger       = logging.getLogger(self.__class__.__name__)

    def load(self) -> tuple[RobotSettings, RobotCalibrationSettings]:
        self._config      = self._service.load_config()
        self._calibration = self._service.load_calibration()
        return self._config, self._calibration

    def save(self, flat: dict, movement_groups: Dict[str, MovementGroup] = None) -> None:
        movement_groups = movement_groups or {}
        updated = RobotSettingsMapper.from_flat_dict(flat, self._config)
        updated.movement_groups = movement_groups
        self._service.save_config(updated)
        self._config = updated
        self._logger.debug("Robot config saved")

        updated_calib = RobotCalibrationMapper.from_flat_dict(flat, self._calibration)
        self._service.save_calibration(updated_calib)
        self._calibration = updated_calib
        self._logger.debug("Robot calibration saved")

from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings
from src.applications.robot_settings.service.i_robot_settings_service import IRobotSettingsService


class RobotSettingsApplicationService(IRobotSettingsService):

    def __init__(
        self,
        settings_service:  ISettingsService,
        config_key:        str,
        calibration_key:   str,
    ):
        self._settings        = settings_service
        self._config_key      = config_key
        self._calibration_key = calibration_key

    def load_config(self) -> RobotSettings:
        return self._settings.get(self._config_key)

    def save_config(self, config: RobotSettings) -> None:
        self._settings.save(self._config_key, config)

    def load_calibration(self) -> RobotCalibrationSettings:
        return self._settings.get(self._calibration_key)

    def save_calibration(self, calibration: RobotCalibrationSettings) -> None:
        self._settings.save(self._calibration_key, calibration)


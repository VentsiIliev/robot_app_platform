from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings
from src.applications.robot_settings.service.i_robot_settings_service import IRobotSettingsService


class RobotSettingsApplicationService(IRobotSettingsService):

    def __init__(self, settings_service: ISettingsService):
        self._settings = settings_service

    def load_config(self) -> RobotSettings:
        return self._settings.get("robot_config")

    def save_config(self, config: RobotSettings) -> None:
        self._settings.save("robot_config", config)

    def load_calibration(self) -> RobotCalibrationSettings:
        return self._settings.get("robot_calibration")

    def save_calibration(self, calibration: RobotCalibrationSettings) -> None:
        self._settings.save("robot_calibration", calibration)

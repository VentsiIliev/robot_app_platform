from abc import ABC, abstractmethod

from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings


class IRobotSettingsService(ABC):

    @abstractmethod
    def load_config(self) -> RobotSettings: ...

    @abstractmethod
    def save_config(self, config: RobotSettings) -> None: ...

    @abstractmethod
    def load_calibration(self) -> RobotCalibrationSettings: ...

    @abstractmethod
    def save_calibration(self, calibration: RobotCalibrationSettings) -> None: ...

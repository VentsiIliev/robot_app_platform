from dataclasses import dataclass

from src.engine.robot.configuration import RobotCalibrationSettings
from src.engine.robot.height_measuring.settings import HeightMeasuringModuleSettings
from src.engine.vision.calibration_vision_settings import CalibrationVisionSettings


@dataclass
class CalibrationSettingsData:
    vision: CalibrationVisionSettings
    robot: RobotCalibrationSettings
    height: HeightMeasuringModuleSettings

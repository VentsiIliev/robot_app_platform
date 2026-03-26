from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.calibration_settings.service.i_calibration_settings_service import (
    ICalibrationSettingsService,
)
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.vision.camera_settings_serializer import CameraSettings


class CalibrationSettingsApplicationService(ICalibrationSettingsService):

    def __init__(self, settings_service: ISettingsService):
        self._settings_service = settings_service

    def load_settings(self) -> CalibrationSettingsData:
        vision = self._settings_service.get(CommonSettingsID.CALIBRATION_VISION_SETTINGS)
        robot = self._settings_service.get(CommonSettingsID.ROBOT_CALIBRATION)
        height = self._settings_service.get(CommonSettingsID.HEIGHT_MEASURING_SETTINGS)
        return CalibrationSettingsData(vision=vision, robot=robot, height=height)

    def save_settings(self, settings: CalibrationSettingsData) -> None:
        self._settings_service.save(CommonSettingsID.CALIBRATION_VISION_SETTINGS, settings.vision)
        self._settings_service.save(CommonSettingsID.ROBOT_CALIBRATION, settings.robot)
        self._settings_service.save(CommonSettingsID.HEIGHT_MEASURING_SETTINGS, settings.height)

        try:
            camera_settings = self._settings_service.get(CommonSettingsID.VISION_CAMERA_SETTINGS)
            if isinstance(camera_settings, CameraSettings):
                merged = dict(camera_settings.data)
                merged.update(settings.vision.to_dict())
                self._settings_service.save(CommonSettingsID.VISION_CAMERA_SETTINGS, CameraSettings(data=merged))
        except Exception:
            pass

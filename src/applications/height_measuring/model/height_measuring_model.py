from typing import Optional

import numpy as np

from src.applications.base.i_application_model import IApplicationModel
from src.applications.height_measuring.service.i_height_measuring_app_service import (
    IHeightMeasuringAppService,
    LaserDetectionResult,
)
from src.engine.robot.height_measuring.settings import HeightMeasuringModuleSettings


class HeightMeasuringModel(IApplicationModel):

    def __init__(self, service: IHeightMeasuringAppService):
        self._service = service

    def load(self) -> HeightMeasuringModuleSettings:
        return self._service.get_settings()

    def save(self, settings: HeightMeasuringModuleSettings = None, **kwargs) -> None:
        if settings is not None:
            self._service.save_settings(settings)

    def run_calibration(self) -> tuple[bool, str]:
        return self._service.run_calibration()

    def is_calibrated(self) -> bool:
        return self._service.is_calibrated()

    def get_calibration_info(self) -> Optional[dict]:
        return self._service.get_calibration_info()

    def get_settings(self) -> HeightMeasuringModuleSettings:
        return self._service.get_settings()

    def save_settings(self, settings: HeightMeasuringModuleSettings) -> tuple[bool, str]:
        return self._service.save_settings(settings)

    def get_latest_frame(self) -> Optional[np.ndarray]:
        return self._service.get_latest_frame()

    def reload_calibration(self) -> None:
        self._service.reload_calibration()

    def laser_on(self) -> tuple[bool, str]:
        return self._service.laser_on()

    def laser_off(self) -> tuple[bool, str]:
        return self._service.laser_off()

    def detect_once(self) -> LaserDetectionResult:
        return self._service.detect_once()

    def cleanup(self) -> None:
        self._service.cleanup()

    def cancel_calibration(self) -> None:
        self._service.cancel_calibration()


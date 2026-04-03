from __future__ import annotations

from typing import Optional

import numpy as np

from src.applications.base.i_application_model import IApplicationModel
from src.applications.hand_eye_calibration.service.i_hand_eye_service import (
    HandEyeConfig,
    IHandEyeCalibrationService,
)


class HandEyeModel(IApplicationModel):

    def __init__(self, service: IHandEyeCalibrationService):
        self._service = service

    def load(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        pass

    def start_capture(self) -> None:
        self._service.start_capture()

    def stop_capture(self) -> None:
        self._service.stop_capture()

    def is_running(self) -> bool:
        return self._service.is_running()

    def get_latest_annotated_frame(self) -> Optional[np.ndarray]:
        return self._service.get_latest_annotated_frame()

    def get_config(self) -> HandEyeConfig:
        return self._service.get_config()

    def save_config(self, config: HandEyeConfig) -> None:
        self._service.save_config(config)

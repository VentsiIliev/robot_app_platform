from __future__ import annotations

from typing import Optional

import numpy as np

from src.applications.base.i_application_model import IApplicationModel
from src.applications.intrinsic_calibration_capture.service.i_intrinsic_capture_service import (
    IIntrinsicCaptureService,
    IntrinsicCaptureConfig,
)


class IntrinsicCaptureModel(IApplicationModel):

    def __init__(self, service: IIntrinsicCaptureService):
        self._service = service

    # ── IApplicationModel ─────────────────────────────────────────────────────

    def load(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        pass

    # ── Domain ────────────────────────────────────────────────────────────────

    def start_capture(self) -> None:
        self._service.start_capture()

    def stop_capture(self) -> None:
        self._service.stop_capture()

    def is_running(self) -> bool:
        return self._service.is_running()

    def get_latest_frame(self) -> Optional[np.ndarray]:
        return self._service.get_latest_frame()

    def get_config(self) -> IntrinsicCaptureConfig:
        return self._service.get_config()

    def save_config(self, config: IntrinsicCaptureConfig) -> None:
        self._service.save_config(config)

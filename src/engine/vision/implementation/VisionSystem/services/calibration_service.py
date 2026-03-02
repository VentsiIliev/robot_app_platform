import logging
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from src.engine.vision.implementation.VisionSystem.core.settings.CameraSettings import CameraSettings
from src.engine.vision.implementation.VisionSystem.features.calibration.cameraCalibration.CameraCalibrationService import \
    CameraCalibrationService as _InternalCalibrationService

_logger = logging.getLogger(__name__)


@dataclass
class CalibrationOutcome:
    success:                 bool
    message:                 str
    camera_matrix:           Optional[np.ndarray] = field(default=None)
    distortion_coefficients: Optional[np.ndarray] = field(default=None)
    perspective_matrix:      Optional[np.ndarray] = field(default=None)


class CalibrationService:

    def __init__(
        self,
        camera_settings:   CameraSettings,
        storage_path:      str,
        message_publisher  = None,
        messaging_service  = None,
    ):
        self._settings    = camera_settings
        self._storage     = storage_path
        self._publisher   = message_publisher
        self._messaging   = messaging_service
        self._images:     List[np.ndarray] = []

    def capture_image(self, raw_image: Optional[np.ndarray]) -> tuple[bool, str]:
        if raw_image is None:
            _logger.warning("No raw image available for calibration capture")
            return False, "No image available"
        self._images.append(raw_image)
        if self._publisher:
            self._publisher.publish_latest_image(raw_image)
        _logger.info("Calibration image captured (%d total)", len(self._images))
        return True, "Calibration image captured successfully"

    def calibrate(self, raw_image: Optional[np.ndarray]) -> CalibrationOutcome:
        draw_was_enabled = self._settings.get_draw_contours()
        self._settings.set_draw_contours(False)

        try:
            svc = _InternalCalibrationService(
                chessboardWidth   = self._settings.get_chessboard_width(),
                chessboardHeight  = self._settings.get_chessboard_height(),
                squareSizeMM      = self._settings.get_square_size_mm(),
                skipFrames        = self._settings.get_calibration_skip_frames(),
                message_publisher = self._publisher,
                storagePath       = self._storage,
                messaging_service = self._messaging,
            )
            svc.calibrationImages = self._images
            result = svc.run(raw_image)
            self._images.clear()
            _logger.info("Calibration images cleared")

            if not result.success:
                _logger.warning("Calibration failed: %s", result.message)
                return CalibrationOutcome(success=False, message=result.message)

            return CalibrationOutcome(
                success                 = True,
                message                 = result.message,
                camera_matrix           = result.camera_matrix,
                distortion_coefficients = result.distortion_coefficients,
                perspective_matrix      = result.perspective_matrix,
            )
        finally:
            if draw_was_enabled:
                self._settings.set_draw_contours(True)
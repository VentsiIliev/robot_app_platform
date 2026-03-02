import logging
from typing import Optional, Tuple

import cv2
import numpy as np

from src.engine.vision.implementation.plvision.PLVision.arucoModule import ArucoDictionary, ArucoDetector
from src.engine.vision.implementation.VisionSystem.core.settings.CameraSettings import CameraSettings

_logger = logging.getLogger(__name__)


class ArucoDetectionService:

    def __init__(self, camera_settings: CameraSettings):
        self._settings = camera_settings

    def detect(
        self,
        corrected_image: Optional[np.ndarray],
        flip:  Optional[bool] = None,
        image: Optional[np.ndarray] = None,
    ) -> Tuple:
        if flip is None:
            flip = self._settings.get_aruco_flip_image()

        draw_was_enabled = self._settings.get_draw_contours()
        self._settings.set_draw_contours(False)

        try:
            target = image if image is not None else corrected_image
            if target is None:
                _logger.warning("No image available for ArUco detection")
                return None, None, None

            if flip:
                target = cv2.flip(target, 1)

            aruco_dict = getattr(
                ArucoDictionary,
                self._settings.get_aruco_dictionary(),
                ArucoDictionary.DICT_4X4_1000,
            )
            detector = ArucoDetector(arucoDict=aruco_dict)
            corners, ids = detector.detectAll(target)
            _logger.info("Detected %d ArUco markers", len(ids))
            return corners, ids, target
        except Exception as exc:
            _logger.exception("ArUco detection failed: %s", exc)
            return None, None, None
        finally:
            if draw_was_enabled:
                self._settings.set_draw_contours(True)
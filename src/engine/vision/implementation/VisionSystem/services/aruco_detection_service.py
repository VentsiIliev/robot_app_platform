import logging
from typing import Optional, Tuple

import cv2
import numpy as np

from src.engine.vision.implementation.plvision.PLVision.arucoModule import ArucoDictionary
from src.engine.vision.implementation.VisionSystem.core.settings.CameraSettings import CameraSettings

_logger = logging.getLogger(__name__)


class ArucoDetectionService:

    def __init__(self, camera_settings: CameraSettings):
        self._settings = camera_settings

    def detect(
        self,
        corrected_image: Optional[np.ndarray],
        flip: Optional[bool] = None,
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

            aruco_dict_entry = getattr(
                ArucoDictionary,
                self._settings.get_aruco_dictionary(),
                ArucoDictionary.DICT_4X4_1000,
            )

            # Build the detector directly so we can control DetectorParameters.
            # CORNER_REFINE_SUBPIX applies sub-pixel refinement inside the ArUco
            # pipeline using marker-aware context — much more stable than calling
            # cv2.cornerSubPix manually on the raw image after detection, which
            # drifts corners to wrong local gradient minima and degrades detection.
            dictionary = cv2.aruco.getPredefinedDictionary(aruco_dict_entry.value)
            params     = cv2.aruco.DetectorParameters()
            params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
            detector   = cv2.aruco.ArucoDetector(dictionary, params)

            corners, ids, _ = detector.detectMarkers(target)
            # detectMarkers returns None when nothing found — normalise to empty list
            if ids is None:
                ids = []

            _logger.info("Detected %d ArUco markers", len(ids))
            return corners, ids, target
        except Exception as exc:
            _logger.exception("ArUco detection failed: %s", exc)
            return None, None, None
        finally:
            if draw_was_enabled:
                self._settings.set_draw_contours(True)

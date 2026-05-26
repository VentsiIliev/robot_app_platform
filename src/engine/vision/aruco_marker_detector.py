from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArucoMarkerCenter:
    marker_id: int
    x_px: float
    y_px: float


def detect_aruco_marker_center(
    image: np.ndarray,
    *,
    marker_id: int,
    dictionary_name: str = "DICT_4X4_1000",
) -> ArucoMarkerCenter | None:
    """Detect one ArUco marker center with a fixed OpenCV dictionary."""
    if image is None:
        return None
    dictionary_id = getattr(cv2.aruco, str(dictionary_name), cv2.aruco.DICT_4X4_1000)
    dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    params.cornerRefinementWinSize = 7
    params.cornerRefinementMaxIterations = 50
    params.cornerRefinementMinAccuracy = 0.01
    params.adaptiveThreshWinSizeMin = 5
    params.adaptiveThreshWinSizeMax = 41
    params.adaptiveThreshWinSizeStep = 4
    params.minMarkerPerimeterRate = 0.015
    params.minOtsuStdDev = 3.0
    params.detectInvertedMarker = True
    params.errorCorrectionRate = 0.7
    detector = cv2.aruco.ArucoDetector(dictionary, params)
    corners, ids, _ = detector.detectMarkers(image)
    if ids is None or len(ids) == 0:
        return None
    target_id = int(marker_id)
    for detected_id, marker_corners in zip(ids.flatten(), corners):
        if int(detected_id) != target_id:
            continue
        center = np.asarray(marker_corners[0], dtype=float).mean(axis=0)
        return ArucoMarkerCenter(marker_id=target_id, x_px=float(center[0]), y_px=float(center[1]))
    _logger.debug("ArUco marker %d not found among detected ids %s", target_id, ids.flatten().tolist())
    return None

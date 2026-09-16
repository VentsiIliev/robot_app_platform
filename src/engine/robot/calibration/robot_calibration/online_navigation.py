"""Guarded in-memory navigation model used while collecting calibration points."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import cv2
import numpy as np


_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OnlineNavigationPrediction:
    robot_xy: tuple[float, float]
    sample_count: int
    median_training_error_mm: float


def predict_robot_xy(context, marker_id: int) -> OnlineNavigationPrediction | None:
    """Predict marker robot XY from accepted training correspondences.

    The model is deliberately ephemeral and never replaces the final calibration
    artifact. Validation markers are excluded from fitting.
    """
    camera_points = context.artifacts.camera_points_for_homography
    robot_positions = context.artifacts.robot_positions_for_calibration
    training_ids = {
        int(value) for value in (context.target_plan.homography_marker_ids or [])
    }
    accepted_ids = sorted(
        marker
        for marker in training_ids
        if marker in camera_points and marker in robot_positions
    )
    if len(accepted_ids) < 4 or int(marker_id) not in camera_points:
        return None

    src = np.asarray([camera_points[key] for key in accepted_ids], dtype=np.float64).reshape(-1, 1, 2)
    dst = np.asarray([robot_positions[key][:2] for key in accepted_ids], dtype=np.float64).reshape(-1, 1, 2)

    image_width = float(context.vision_service.get_camera_width())
    image_height = float(context.vision_service.get_camera_height())
    hull_area = float(cv2.contourArea(cv2.convexHull(src.astype(np.float32))))
    if hull_area < image_width * image_height * 0.02:
        return None

    matrix, status = cv2.findHomography(src, dst, cv2.RANSAC, 2.0)
    if matrix is None or not np.all(np.isfinite(matrix)):
        return None

    fitted = cv2.perspectiveTransform(src, matrix).reshape(-1, 2)
    errors = np.linalg.norm(fitted - dst.reshape(-1, 2), axis=1)
    median_error = float(np.median(errors))
    if median_error > 2.0 or float(np.max(errors)) > 5.0:
        _logger.info(
            "Online navigation homography rejected: samples=%d median=%.3fmm max=%.3fmm",
            len(accepted_ids), median_error, float(np.max(errors)),
        )
        return None

    target_px = np.asarray(camera_points[int(marker_id)], dtype=np.float64).reshape(1, 1, 2)
    predicted = cv2.perspectiveTransform(target_px, matrix).reshape(2)
    if not np.all(np.isfinite(predicted)):
        return None
    return OnlineNavigationPrediction(
        robot_xy=(float(predicted[0]), float(predicted[1])),
        sample_count=len(accepted_ids),
        median_training_error_mm=median_error,
    )

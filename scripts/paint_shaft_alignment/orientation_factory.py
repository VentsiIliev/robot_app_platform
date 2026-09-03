from __future__ import annotations

import os

import cv2
import numpy as np

from .config import StandaloneShaftDetectionConfig
from .orientation import (
    ComparingOrientationStrategy,
    CornerEdgeOrientationStrategy,
    SolvePnPOrientationStrategy,
)


def build_orientation_strategy(vision_service, config: StandaloneShaftDetectionConfig):
    strategy_name = config.orientation_strategy.strip().lower()
    if strategy_name == "corner_edge":
        return CornerEdgeOrientationStrategy()
    if strategy_name not in {"solve_pnp", "compare"}:
        raise ValueError(f"Unsupported orientation strategy: {config.orientation_strategy!r}")

    calibration_path = os.path.join(
        os.path.dirname(vision_service.camera_to_robot_matrix_path),
        "camera_calibration.npz",
    )
    with np.load(calibration_path) as calibration:
        camera_matrix = np.asarray(calibration["mtx"], dtype=np.float64)
        distortion = np.asarray(calibration["dist"], dtype=np.float64)

    if not config.raw_mode:
        image_size = (
            int(vision_service.get_camera_width()),
            int(vision_service.get_camera_height()),
        )
        camera_matrix, _roi = cv2.getOptimalNewCameraMatrix(
            camera_matrix,
            distortion,
            image_size,
            0.5,
            image_size,
        )
        distortion = np.zeros_like(distortion)

    solve_pnp = SolvePnPOrientationStrategy(
        marker_size_mm=config.marker_size_mm,
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion,
    )
    if strategy_name == "solve_pnp":
        return solve_pnp
    return ComparingOrientationStrategy(
        (CornerEdgeOrientationStrategy(), solve_pnp),
        primary_name=config.orientation_primary_strategy,
    )

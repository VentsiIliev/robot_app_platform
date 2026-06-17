from __future__ import annotations

from logging import Logger
from typing import Callable

import cv2
import numpy as np

from src.engine.robot.path_preparation import config


class HomographyOnlyPreviewStrategy:
    """Build a homography-only path for pixel-to-mm debug comparisons."""

    def convert(
        self,
        pts_px: np.ndarray,
        settings: dict,
        *,
        segment_config,
        z_min: float,
        base_position: list[float] | None,
        transformer,
        resolver,
        pixel_height_compensation_fn: Callable[[float], tuple[float, float]] | None,
        logger: Logger,
    ) -> list:
        try:
            defaults = segment_config.schema.get_defaults()
            spray_height = float(
                str(settings.get("spraying_height", defaults.get("spraying_height", "0"))).replace(",", "")
            )
            base_z = base_position[2] + spray_height if base_position is not None else float(z_min) + spray_height
            rz_offset = float(settings.get("rz_angle", defaults.get("rz_angle", "0")))
        except (ValueError, TypeError):
            return []

        base_transformer = getattr(resolver, "_base", None) if resolver is not None else transformer
        model = getattr(base_transformer, "_model", None)
        homography_matrix = getattr(model, "homography_matrix", None)
        if homography_matrix is None:
            return []
        try:
            homography = np.asarray(homography_matrix, dtype=np.float64).reshape(3, 3)
        except (TypeError, ValueError):
            logger.debug("[EXECUTE] Homography-only debug matrix is unavailable or invalid", exc_info=True)
            return []

        pts = np.asarray(pts_px, dtype=np.float64).reshape(-1, 2)
        workpiece_height_mm = _safe_float(settings.get("height_mm"), config._DEFAULT_WORKPIECE_HEIGHT_MM)
        if callable(pixel_height_compensation_fn) and abs(workpiece_height_mm) > 1e-9:
            try:
                compensation_dx_px, compensation_dy_px = pixel_height_compensation_fn(workpiece_height_mm)
                pts = pts.copy()
                pts[:, 0] -= float(compensation_dx_px)
                pts[:, 1] -= float(compensation_dy_px)
            except Exception:
                logger.debug(
                    "[EXECUTE] Failed to apply pixel height compensation for homography-only debug",
                    exc_info=True,
                )

        xy = cv2.perspectiveTransform(
            pts.astype(np.float32).reshape(-1, 1, 2),
            homography,
        ).reshape(-1, 2)
        rx, ry = _base_orientation_xy(base_position)
        return [
            [float(x), float(y), float(base_z), float(rx), float(ry), float(rz_offset)]
            for x, y in xy
        ]


def _safe_float(value, default: float) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _base_orientation_xy(base_position: list[float] | None) -> tuple[float, float]:
    if base_position is not None and len(base_position) >= 5:
        return float(base_position[3]), float(base_position[4])
    return 180.0, 0.0

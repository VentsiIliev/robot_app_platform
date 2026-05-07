from __future__ import annotations

import copy
import logging

import numpy as np

_logger = logging.getLogger(__name__)


def estimate_local_image_basis(transformer, image_width: float, image_height: float) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Estimate local image pixel basis vectors from the active image-to-robot transformer."""
    if transformer is None or not transformer.is_available():
        return None

    center_px = np.array([float(image_width) * 0.5, float(image_height) * 0.5], dtype=float)
    try:
        center_robot = np.asarray(transformer.transform(float(center_px[0]), float(center_px[1])), dtype=float)
        pixel_origin = np.asarray(
            transformer.inverse_transform(float(center_robot[0]), float(center_robot[1])),
            dtype=float,
        )
        pixel_x = np.asarray(
            transformer.inverse_transform(float(center_robot[0] + 1.0), float(center_robot[1])),
            dtype=float,
        )
        pixel_y = np.asarray(
            transformer.inverse_transform(float(center_robot[0]), float(center_robot[1] + 1.0)),
            dtype=float,
        )
        basis_x = pixel_x - pixel_origin
        basis_y = pixel_y - pixel_origin
        if float(np.linalg.norm(basis_x)) > 1e-6 and float(np.linalg.norm(basis_y)) > 1e-6:
            return pixel_origin, basis_x, basis_y
    except Exception:
        _logger.debug("Failed to estimate local image basis from transformer", exc_info=True)
    return None


def map_raw_workpiece_mm_to_image(raw: dict, image_width: float, image_height: float, transformer) -> dict:
    """Recenter a raw workpiece described in mm into image pixel space for preview/alignment."""
    placed = copy.deepcopy(raw)
    contour = placed.get("contour") or []
    points = [point[0] for point in contour if point and point[0]]
    if not points:
        return placed

    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    contour_center_mm = np.array([0.5 * (min(xs) + max(xs)), 0.5 * (min(ys) + max(ys))], dtype=float)

    image_center = np.array([float(image_width) * 0.5, float(image_height) * 0.5], dtype=float)
    basis = estimate_local_image_basis(transformer, float(image_width), float(image_height))
    if basis is None:
        basis_x = np.array([1.0, 0.0], dtype=float)
        basis_y = np.array([0.0, 1.0], dtype=float)
    else:
        _pixel_origin, basis_x, basis_y = basis

    def _map_contour(contour_array):
        for point in contour_array or []:
            if point and point[0]:
                local_mm = np.array(
                    [
                        float(point[0][0]) - float(contour_center_mm[0]),
                        float(point[0][1]) - float(contour_center_mm[1]),
                    ],
                    dtype=float,
                )
                mapped = image_center + local_mm[0] * basis_x + local_mm[1] * basis_y
                point[0][0] = float(mapped[0])
                point[0][1] = float(mapped[1])

    _map_contour(placed.get("contour"))
    spray = placed.get("sprayPattern") or {}
    for key in ("Contour", "Fill"):
        for segment in spray.get(key, []):
            _map_contour(segment.get("contour"))
    return placed

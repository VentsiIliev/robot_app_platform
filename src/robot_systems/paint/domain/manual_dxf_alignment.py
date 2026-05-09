from __future__ import annotations

import copy
from typing import Any

import numpy as np

from src.robot_systems.paint.processes.paint.align import _extract_raw_contour_points


def apply_manual_similarity_transform_to_raw(
    raw: dict,
    *,
    rotation_deg: float = 0.0,
    scale: float = 1.0,
    translation_x_px: float = 0.0,
    translation_y_px: float = 0.0,
) -> dict:
    """Return a copy of raw workpiece data with a manual image-space transform applied."""
    transformed = copy.deepcopy(raw)
    source_points = _extract_raw_contour_points(transformed)
    if len(source_points) < 1:
        return transformed

    center = np.mean(source_points, axis=0)
    theta = float(np.deg2rad(float(rotation_deg)))
    safe_scale = max(1e-6, float(scale))
    translation = np.asarray([float(translation_x_px), float(translation_y_px)], dtype=np.float64)

    _transform_contour_payload(
        transformed.get("contour"),
        center=center,
        theta=theta,
        scale=safe_scale,
        translation=translation,
    )

    spray = transformed.get("sprayPattern") or {}
    for key in ("Contour", "Fill"):
        for segment in spray.get(key, []) or []:
            _transform_contour_payload(
                segment.get("contour"),
                center=center,
                theta=theta,
                scale=safe_scale,
                translation=translation,
            )

    if transformed.get("pickupPoint") is not None:
        pickup = _parse_pickup_point(transformed.get("pickupPoint"))
        if pickup is not None:
            mapped = _transform_points(
                np.asarray([pickup], dtype=np.float64),
                center=center,
                theta=theta,
                scale=safe_scale,
                translation=translation,
            )[0]
            transformed["pickupPoint"] = [float(mapped[0]), float(mapped[1])]

    return transformed


def _transform_contour_payload(
    contour_array: Any,
    *,
    center: np.ndarray,
    theta: float,
    scale: float,
    translation: np.ndarray,
) -> None:
    if contour_array is None:
        return
    for index, point in enumerate(contour_array):
        if point is None:
            continue
        arr = np.asarray(point, dtype=np.float64)
        if arr.size < 2:
            continue
        flat = arr.reshape(-1)
        vec = np.asarray([[float(flat[0]), float(flat[1])]], dtype=np.float64)
        mapped = _transform_points(
            vec,
            center=center,
            theta=theta,
            scale=scale,
            translation=translation,
        )[0]
        if isinstance(point, np.ndarray):
            point.reshape(-1)[0] = float(mapped[0])
            point.reshape(-1)[1] = float(mapped[1])
        else:
            contour_array[index] = [[float(mapped[0]), float(mapped[1])]]


def _transform_points(
    points: np.ndarray,
    *,
    center: np.ndarray,
    theta: float,
    scale: float,
    translation: np.ndarray,
) -> np.ndarray:
    rotation = np.array(
        [
            [np.cos(theta), -np.sin(theta)],
            [np.sin(theta), np.cos(theta)],
        ],
        dtype=np.float64,
    )
    return ((np.asarray(points, dtype=np.float64) - center) @ rotation.T) * float(scale) + center + translation


def _parse_pickup_point(value) -> tuple[float, float] | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            x_str, y_str = value.split(",", 1)
            return float(x_str), float(y_str)
        except (TypeError, ValueError):
            return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError):
            return None
    if isinstance(value, dict):
        try:
            return float(value["x"]), float(value["y"])
        except (KeyError, TypeError, ValueError):
            return None
    return None

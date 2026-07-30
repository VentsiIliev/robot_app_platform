from __future__ import annotations

import numpy as np

from src.robot_systems.paint.processes.paint.align.alignment.sampling import (
    _resample_closed_path,
)


def _main_contour_payload(raw: dict):
    """Return the raw main contour list, unwrapping compatibility wrapper payloads."""
    contour = (raw or {}).get("contour")
    if isinstance(contour, dict):
        nested = contour.get("contour")
        if nested is not None:
            return nested
    if contour is None:
        return []
    return contour


def _extract_raw_contour_points(raw: dict) -> np.ndarray:
    """Extract the main raw workpiece contour as an Nx2 numpy array."""
    contour = _main_contour_payload(raw)
    points: list[list[float]] = []
    for point in contour:
        if point is None:
            continue
        arr = np.asarray(point, dtype=np.float64)
        if arr.size < 2:
            continue
        flat = arr.reshape(-1)
        points.append([float(flat[0]), float(flat[1])])
    if not points:
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray(points, dtype=np.float64)


def _normalize_contour_points(contour) -> np.ndarray:
    """Normalize OpenCV-style contour arrays into a simple Nx2 float array."""
    array = np.asarray(contour, dtype=np.float64)
    if array.ndim == 3 and array.shape[1] == 1:
        array = array[:, 0, :]
    if array.ndim != 2 or array.shape[1] < 2:
        return np.empty((0, 2), dtype=np.float64)
    return array[:, :2]


def _resample_raw_contour_payload(contour_array, count: int) -> np.ndarray:
    """Convert a raw contour payload into a resampled Nx2 contour for smoothing."""
    points = []
    if contour_array is None:
        return np.empty((0, 2), dtype=np.float64)
    for point in contour_array:
        if point is None:
            continue
        arr = np.asarray(point, dtype=np.float64)
        if arr.size < 2:
            continue
        flat = arr.reshape(-1)
        points.append([float(flat[0]), float(flat[1])])
    if len(points) < 3:
        return np.empty((0, 2), dtype=np.float64)
    return _resample_closed_path(np.asarray(points, dtype=np.float64), count)


def _raw_contour_payload_points(contour_array) -> np.ndarray:
    """Convert a raw contour payload into an Nx2 contour without changing ordering."""
    points = []
    if contour_array is None:
        return np.empty((0, 2), dtype=np.float64)
    for point in contour_array:
        if point is None:
            continue
        arr = np.asarray(point, dtype=np.float64)
        if arr.size < 2:
            continue
        flat = arr.reshape(-1)
        points.append([float(flat[0]), float(flat[1])])
    if len(points) < 3:
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray(points, dtype=np.float64)


def _replace_raw_contour_payload(contour_array, points: np.ndarray) -> None:
    """Rewrite a raw contour payload from an Nx2 point array."""
    contour_array[:] = [
        [[float(point[0]), float(point[1])]]
        for point in np.asarray(points, dtype=np.float64)
    ]

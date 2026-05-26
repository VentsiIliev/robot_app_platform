from __future__ import annotations

from typing import Iterable

import numpy as np


def contours_to_calibrated_mm(contours: Iterable, transformer) -> list[np.ndarray]:
    """Convert image contours to calibrated millimeter coordinates."""
    if transformer is None or not getattr(transformer, "is_available", lambda: False)():
        raise RuntimeError("Calibration transform is not available")

    converted: list[np.ndarray] = []
    for contour in contours or []:
        points = _contour_points(contour)
        if len(points) < 3:
            continue
        mapped = [transformer.transform(float(x), float(y)) for x, y in points]
        converted.append(np.asarray([[[float(x), float(y)]] for x, y in mapped], dtype=np.float64))
    return converted


def _contour_points(contour) -> list[tuple[float, float]]:
    try:
        array = np.asarray(contour, dtype=float)
    except Exception:
        return []
    if array.size == 0:
        return []
    array = array.reshape(-1, array.shape[-1] if array.ndim > 1 else 1)
    if array.shape[1] < 2:
        return []
    return [(float(point[0]), float(point[1])) for point in array[:, :2]]

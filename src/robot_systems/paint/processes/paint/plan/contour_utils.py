from __future__ import annotations

from typing import Iterable

import cv2
import numpy as np

from src.robot_systems.paint.processes.paint.align import _normalize_contour_points


def pick_largest_contour(contours: Iterable) -> np.ndarray | None:
    """Return the contour with the largest valid area from a captured contour set."""
    best = None
    best_area = -1.0
    for contour in contours or []:
        try:
            arr = np.asarray(contour, dtype=np.float32)
            area = float(cv2.contourArea(arr))
        except Exception:
            continue
        if area > best_area:
            best_area = area
            best = arr
    return best


def contour_to_workpiece_raw(
    contour: np.ndarray,
    *,
    workpiece_id: str = "captured",
    name: str = "Captured contour",
    height_mm: float = 0.0,
) -> dict:
    """Wrap a captured contour into the raw workpiece payload shape used by paint execution."""
    normalized = _normalize_contour_points(contour)
    return {
        "workpieceId": str(workpiece_id),
        "name": str(name),
        "height_mm": float(height_mm),
        "contour": [
            [[float(point[0]), float(point[1])]]
            for point in normalized
        ],
        "sprayPattern": {"Contour": [], "Fill": []},
    }


def extract_points_for_log(raw: dict) -> np.ndarray:
    contour = (raw or {}).get("contour")
    if isinstance(contour, dict):
        contour = contour.get("contour")
    try:
        array = np.asarray(contour if contour is not None else [], dtype=np.float64)
    except Exception:
        return np.empty((0, 2), dtype=np.float64)
    if array.ndim == 3 and array.shape[1] == 1:
        array = array[:, 0, :]
    if array.ndim != 2 or array.shape[1] < 2:
        points: list[list[float]] = []
        iterable = contour if contour is not None else []
        for point in iterable:
            try:
                flat = np.asarray(point, dtype=np.float64).reshape(-1)
            except Exception:
                continue
            if flat.size >= 2:
                points.append([float(flat[0]), float(flat[1])])
        return np.asarray(points, dtype=np.float64) if points else np.empty((0, 2), dtype=np.float64)
    return array[:, :2]


def describe_contour(points: np.ndarray) -> str:
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] < 2:
        return "count=0"
    pts = points[:, :2]
    mins = np.min(pts, axis=0)
    maxs = np.max(pts, axis=0)
    centroid = np.mean(pts, axis=0)
    area = 0.0
    if len(pts) >= 3:
        x = pts[:, 0]
        y = pts[:, 1]
        area = 0.5 * float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))
    return (
        f"count={len(pts)} "
        f"centroid=({float(centroid[0]):.3f}, {float(centroid[1]):.3f}) "
        f"bbox=({float(mins[0]):.3f}, {float(mins[1]):.3f})-({float(maxs[0]):.3f}, {float(maxs[1]):.3f}) "
        f"area={float(area):.3f}"
    )

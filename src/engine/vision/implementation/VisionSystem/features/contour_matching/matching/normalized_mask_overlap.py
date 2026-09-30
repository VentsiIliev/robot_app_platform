"""Compare contour silhouettes independently of position, rotation, and scale."""

import cv2
import numpy as np


_TARGET_AREA = 12000.0
_PADDING = 20
_MAX_CANVAS_SIZE = 1024


def normalized_mask_overlap(first, second) -> float:
    """Return the best filled-mask intersection over union over planar rotations."""
    first_points = np.asarray(first, dtype=np.float32).reshape(-1, 1, 2)
    second_points = np.asarray(second, dtype=np.float32).reshape(-1, 1, 2)
    if len(first_points) < 3 or len(second_points) < 3:
        return 0.0

    normalized = [_center_and_scale(points) for points in (first_points, second_points)]
    if any(points is None for points in normalized):
        return 0.0

    radius = max(float(np.linalg.norm(points, axis=1).max()) for points in normalized)
    size = max(128, int(np.ceil(2 * radius + 2 * _PADDING)))
    if size > _MAX_CANVAS_SIZE:
        return 0.0
    center = (size / 2.0, size / 2.0)
    first_mask, second_mask = (_filled_mask(points, size, center) for points in normalized)

    best_angle = 0
    best_overlap = 0.0
    for angle in range(0, 360, 15):
        overlap = _rotated_overlap(first_mask, second_mask, center, angle)
        if overlap > best_overlap:
            best_angle, best_overlap = angle, overlap

    for offset in range(-10, 11):
        angle = best_angle + offset
        best_overlap = max(
            best_overlap,
            _rotated_overlap(first_mask, second_mask, center, angle),
        )
    return best_overlap


def _center_and_scale(points: np.ndarray) -> np.ndarray | None:
    area = cv2.contourArea(points)
    if area <= 0:
        return None
    moments = cv2.moments(points)
    if abs(moments["m00"]) < 1e-9:
        return None
    centroid = np.array(
        [moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]],
        dtype=np.float32,
    )
    return (points.reshape(-1, 2) - centroid) * np.sqrt(_TARGET_AREA / area)


def _filled_mask(points: np.ndarray, size: int, center: tuple[float, float]) -> np.ndarray:
    shifted = np.rint(points + center).astype(np.int32)
    mask = np.zeros((size, size), dtype=np.uint8)
    cv2.fillPoly(mask, [shifted], 1)
    return mask


def _rotated_overlap(
    first_mask: np.ndarray,
    second_mask: np.ndarray,
    center: tuple[float, float],
    angle: float,
) -> float:
    size = first_mask.shape[0]
    rotation = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        first_mask, rotation, (size, size), flags=cv2.INTER_NEAREST
    )
    intersection = cv2.countNonZero(cv2.bitwise_and(rotated, second_mask))
    union = cv2.countNonZero(cv2.bitwise_or(rotated, second_mask))
    return intersection / union if union else 0.0

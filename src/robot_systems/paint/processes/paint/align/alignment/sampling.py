from __future__ import annotations

import numpy as np


def _resample_closed_path(points: np.ndarray, count: int) -> np.ndarray:
    """Resample a closed contour to a fixed number of evenly spaced points."""
    if len(points) < 2:
        return points

    closed_points = points
    if np.linalg.norm(points[0] - points[-1]) > 1e-6:
        closed_points = np.vstack([points, points[0]])

    segment_lengths = np.linalg.norm(np.diff(closed_points, axis=0), axis=1)
    total_length = float(np.sum(segment_lengths))
    if total_length <= 1e-9:
        return closed_points[:-1]

    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    samples = np.linspace(0.0, total_length, num=max(int(count), 3), endpoint=False)

    resampled = []
    seg_index = 0
    for sample in samples:
        while seg_index + 1 < len(cumulative) and cumulative[seg_index + 1] < sample:
            seg_index += 1

        seg_start = closed_points[seg_index]
        seg_end = closed_points[seg_index + 1]
        seg_len = segment_lengths[seg_index]

        if seg_len <= 1e-9:
            resampled.append(seg_start.copy())
            continue

        ratio = (sample - cumulative[seg_index]) / seg_len
        resampled.append(seg_start + ratio * (seg_end - seg_start))

    return np.asarray(resampled, dtype=np.float64)


def _polygon_area(points: np.ndarray) -> float:
    """Return absolute polygon area for a closed contour sample."""
    if len(points) < 3:
        return 0.0
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _path_length(points: np.ndarray) -> float:
    """Return perimeter/closed path length for a contour sample."""
    if len(points) < 2:
        return 0.0
    closed = points if np.linalg.norm(points[0] - points[-1]) <= 1e-6 else np.vstack([points, points[0]])
    return float(np.sum(np.linalg.norm(np.diff(closed, axis=0), axis=1)))


def _describe_contour(points: np.ndarray) -> str:
    """Return a compact contour summary for diagnostics."""
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] < 2:
        return "count=0"
    pts = points[:, :2]
    mins = np.min(pts, axis=0)
    maxs = np.max(pts, axis=0)
    centroid = np.mean(pts, axis=0)
    area = _polygon_area(pts)
    return (
        f"count={len(pts)} "
        f"centroid=({float(centroid[0]):.3f}, {float(centroid[1]):.3f}) "
        f"bbox=({float(mins[0]):.3f}, {float(mins[1]):.3f})-({float(maxs[0]):.3f}, {float(maxs[1]):.3f}) "
        f"area={float(area):.3f}"
    )


def _laplacian_smooth_closed_path(points: np.ndarray, iterations: int = 2, alpha: float = 0.2) -> np.ndarray:
    """Apply light closed-path Laplacian smoothing without collapsing the contour."""
    smoothed = np.asarray(points, dtype=np.float64).copy()
    if len(smoothed) < 3:
        return smoothed

    alpha = float(np.clip(alpha, 0.0, 1.0))
    for _ in range(max(int(iterations), 0)):
        prev_points = np.roll(smoothed, 1, axis=0)
        next_points = np.roll(smoothed, -1, axis=0)
        neighbor_mean = 0.5 * (prev_points + next_points)
        smoothed = (1.0 - alpha) * smoothed + alpha * neighbor_mean
    return smoothed

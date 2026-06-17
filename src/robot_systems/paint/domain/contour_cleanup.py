from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def clean_straight_contour_noise(
    contour: Any,
    *,
    enabled: bool = True,
    distance_tolerance_px: float = 1.25,
    turn_tolerance_deg: float = 1.0,
    max_passes: int = 6,
    closed: bool = True,
) -> np.ndarray:
    """Remove redundant samples from locally straight contour runs."""
    arr = np.asarray(contour, dtype=np.float32)
    if arr.size == 0:
        return np.zeros((0, 1, 2), dtype=np.float32)
    points = arr.reshape(-1, 2).astype(np.float64)
    if not enabled or len(points) < 4:
        return points.astype(np.float32).reshape(-1, 1, 2)

    had_duplicate_close = bool(len(points) > 2 and np.linalg.norm(points[0] - points[-1]) <= 1e-6)
    if had_duplicate_close:
        points = points[:-1]
    if len(points) < 4:
        return _restore_shape(points, had_duplicate_close)

    distance_tolerance_px = max(0.0, float(distance_tolerance_px))
    turn_tolerance_deg = max(0.0, float(turn_tolerance_deg))
    max_passes = max(1, int(max_passes))

    points = _rdp_simplify_closed(points, distance_tolerance_px) if closed else _rdp_simplify(points, distance_tolerance_px)

    for _ in range(max_passes):
        keep = np.ones(len(points), dtype=bool)
        for index in range(len(points)):
            if not closed and (index == 0 or index == len(points) - 1):
                continue

            prev_index = (index - 1) % len(points)
            next_index = (index + 1) % len(points)
            prev_point = points[prev_index]
            point = points[index]
            next_point = points[next_index]

            if _local_turn_degrees(prev_point, point, next_point) > turn_tolerance_deg:
                continue
            if _point_line_distance(point, prev_point, next_point) > distance_tolerance_px:
                continue
            keep[index] = False

        if bool(np.all(keep)):
            break
        if int(np.count_nonzero(keep)) < 3:
            break
        points = points[keep]

    return _restore_shape(points, had_duplicate_close)


def contour_cleanup_settings(settings: dict | None) -> dict[str, float | bool | int]:
    settings = settings or {}
    return {
        "enabled": _as_bool(settings.get("straight_cleanup_enabled", True), True),
        "distance_tolerance_px": _as_float(settings.get("straight_cleanup_distance_px", 1.25), 1.25),
        "turn_tolerance_deg": _as_float(settings.get("straight_cleanup_turn_deg", 1.0), 1.0),
        "max_passes": max(1, int(_as_float(settings.get("straight_cleanup_max_passes", 6), 6))),
    }


def save_straight_cleanup_debug_plot(
    before_contour: Any,
    after_contour: Any,
    *,
    settings: dict | None = None,
    save_dir: str | os.PathLike[str] | None = None,
) -> str | None:
    before = np.asarray(before_contour, dtype=np.float32)
    after = np.asarray(after_contour, dtype=np.float32)
    if before.size == 0 or after.size == 0:
        return None

    before_xy = before.reshape(-1, 2)
    after_xy = after.reshape(-1, 2)
    target_dir = Path(save_dir) if save_dir else _default_debug_plot_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("MPLCONFIGDIR", "/tmp/robot_app_platform_matplotlib")
    os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    removed_count = max(0, int(len(before_xy) - len(after_xy)))
    before_rect = _min_rect_info(before_xy)
    after_rect = _min_rect_info(after_xy)
    rect_delta = _min_rect_delta(before_rect, after_rect)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = target_dir / f"paint_straight_cleanup_{timestamp}.png"

    fig, (ax_before, ax_after, ax_overlay) = plt.subplots(1, 3, figsize=(18, 6))
    _plot_contour_axis(ax_before, before_xy, f"Before cleanup ({len(before_xy)} pts)", "tab:blue")
    _plot_min_rect(ax_before, before_rect, "tab:orange", "before min rect")
    _plot_contour_axis(ax_after, after_xy, f"After cleanup ({len(after_xy)} pts)", "tab:green")
    _plot_min_rect(ax_after, after_rect, "tab:orange", "after min rect")
    _plot_contour_axis(ax_overlay, before_xy, "Before", "tab:blue", alpha=0.45)
    _plot_contour_axis(ax_overlay, after_xy, "After", "tab:green", alpha=0.95)
    _plot_min_rect(ax_overlay, before_rect, "tab:blue", "before rect", alpha=0.5)
    _plot_min_rect(ax_overlay, after_rect, "tab:green", "after rect", alpha=0.95)
    ax_overlay.set_title(f"Overlay - removed {removed_count} pts")
    ax_overlay.legend()

    cleanup_settings = contour_cleanup_settings(settings)
    fig.suptitle(
        "Paint Straight Cleanup: "
        f"dist={cleanup_settings['distance_tolerance_px']}px, "
        f"turn={cleanup_settings['turn_tolerance_deg']}deg, "
        f"passes={cleanup_settings['max_passes']} | "
        f"rect before={before_rect['major']:.2f}x{before_rect['minor']:.2f}px "
        f"after={after_rect['major']:.2f}x{after_rect['minor']:.2f}px "
        f"delta={rect_delta['major']:+.2f}x{rect_delta['minor']:+.2f}px "
        f"angle_delta={rect_delta['angle']:+.2f}deg"
    )
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return str(path)


def _restore_shape(points: np.ndarray, duplicate_close: bool) -> np.ndarray:
    restored = np.asarray(points, dtype=np.float32)
    if duplicate_close and len(restored) and np.linalg.norm(restored[0] - restored[-1]) > 1e-6:
        restored = np.vstack([restored, restored[:1]])
    return restored.reshape(-1, 1, 2)


def _plot_contour_axis(ax, points: np.ndarray, title: str, color: str, alpha: float = 1.0) -> None:
    ax.plot(points[:, 0], points[:, 1], "o-", color=color, markersize=3, linewidth=1.4, alpha=alpha, label=title)
    ax.scatter(points[0, 0], points[0, 1], s=70, color="green", edgecolors="black", zorder=5, label="start")
    ax.scatter(points[-1, 0], points[-1, 1], s=70, color="red", edgecolors="black", zorder=5, label="end")
    ax.set_title(title)
    ax.set_xlabel("Image X (px)")
    ax.set_ylabel("Image Y (px)")
    ax.grid(True)
    ax.axis("equal")
    ax.invert_yaxis()


def _plot_min_rect(ax, rect_info: dict[str, float | np.ndarray], color: str, label: str, alpha: float = 1.0) -> None:
    box = np.asarray(rect_info["box"], dtype=np.float64)
    if box.shape != (4, 2):
        return
    closed = np.vstack([box, box[:1]])
    ax.plot(closed[:, 0], closed[:, 1], "--", color=color, linewidth=1.5, alpha=alpha, label=label)


def _min_rect_info(points: np.ndarray) -> dict[str, float | np.ndarray]:
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    if len(pts) < 3:
        min_xy = np.min(pts, axis=0) if len(pts) else np.zeros(2, dtype=np.float32)
        max_xy = np.max(pts, axis=0) if len(pts) else np.zeros(2, dtype=np.float32)
        size = max_xy - min_xy
        box = np.asarray(
            [
                [min_xy[0], min_xy[1]],
                [max_xy[0], min_xy[1]],
                [max_xy[0], max_xy[1]],
                [min_xy[0], max_xy[1]],
            ],
            dtype=np.float32,
        )
        return {
            "major": float(max(size[0], size[1])),
            "minor": float(min(size[0], size[1])),
            "angle": 0.0,
            "box": box,
        }

    rect = cv2.minAreaRect(pts)
    width = float(rect[1][0])
    height = float(rect[1][1])
    angle = float(rect[2])
    if height > width:
        width, height = height, width
        angle += 90.0
    return {
        "major": width,
        "minor": height,
        "angle": _normalize_rect_angle(angle),
        "box": cv2.boxPoints(rect).astype(np.float32),
    }


def _min_rect_delta(
    before: dict[str, float | np.ndarray],
    after: dict[str, float | np.ndarray],
) -> dict[str, float]:
    return {
        "major": float(after["major"]) - float(before["major"]),
        "minor": float(after["minor"]) - float(before["minor"]),
        "angle": _angle_delta(float(before["angle"]), float(after["angle"])),
    }


def _normalize_rect_angle(angle: float) -> float:
    value = float(angle)
    while value <= -90.0:
        value += 180.0
    while value > 90.0:
        value -= 180.0
    return value


def _angle_delta(before: float, after: float) -> float:
    delta = float(after) - float(before)
    while delta <= -90.0:
        delta += 180.0
    while delta > 90.0:
        delta -= 180.0
    return delta


def _default_debug_plot_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "bootstrap" / "debug_plots"


def _rdp_simplify(points: np.ndarray, epsilon: float) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 3 or epsilon <= 0.0:
        return pts.copy()

    start = pts[0]
    end = pts[-1]
    distances = np.asarray([_point_line_distance(point, start, end) for point in pts[1:-1]], dtype=np.float64)
    if distances.size == 0:
        return pts[[0, -1]].copy()

    max_offset = int(np.argmax(distances))
    max_distance = float(distances[max_offset])
    if max_distance <= epsilon:
        return pts[[0, -1]].copy()

    split_index = max_offset + 1
    left = _rdp_simplify(pts[:split_index + 1], epsilon)
    right = _rdp_simplify(pts[split_index:], epsilon)
    return np.vstack([left[:-1], right])


def _rdp_simplify_closed(points: np.ndarray, epsilon: float) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 4 or epsilon <= 0.0:
        return pts.copy()

    first, second = _farthest_pair_indices(pts)
    if first == second:
        return pts.copy()

    path_a = _cyclic_path(pts, first, second)
    path_b = _cyclic_path(pts, second, first)
    simplified_a = _rdp_simplify(path_a, epsilon)
    simplified_b = _rdp_simplify(path_b, epsilon)
    combined = np.vstack([simplified_a[:-1], simplified_b[:-1]])
    return _remove_duplicate_consecutive(combined)


def _farthest_pair_indices(points: np.ndarray) -> tuple[int, int]:
    max_distance_sq = -1.0
    best = (0, 0)
    for first in range(len(points)):
        deltas = points[first + 1:] - points[first]
        if len(deltas) == 0:
            continue
        distances_sq = np.einsum("ij,ij->i", deltas, deltas)
        offset = int(np.argmax(distances_sq))
        distance_sq = float(distances_sq[offset])
        if distance_sq > max_distance_sq:
            max_distance_sq = distance_sq
            best = (first, first + 1 + offset)
    return best


def _cyclic_path(points: np.ndarray, start: int, end: int) -> np.ndarray:
    if start <= end:
        return points[start:end + 1].copy()
    return np.vstack([points[start:], points[:end + 1]])


def _remove_duplicate_consecutive(points: np.ndarray) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) < 2:
        return pts.copy()
    keep = [True]
    for index in range(1, len(pts)):
        keep.append(float(np.linalg.norm(pts[index] - pts[index - 1])) > 1e-9)
    return pts[np.asarray(keep, dtype=bool)]


def _point_line_distance(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> float:
    line = end - start
    length = float(np.linalg.norm(line))
    if length <= 1e-9:
        return float(np.linalg.norm(point - start))
    rel = point - start
    return float(abs(line[0] * rel[1] - line[1] * rel[0]) / length)


def _local_turn_degrees(prev_point: np.ndarray, point: np.ndarray, next_point: np.ndarray) -> float:
    incoming = point - prev_point
    outgoing = next_point - point
    in_len = float(np.linalg.norm(incoming))
    out_len = float(np.linalg.norm(outgoing))
    if in_len <= 1e-9 or out_len <= 1e-9:
        return 0.0
    cross = float(incoming[0] * outgoing[1] - incoming[1] * outgoing[0])
    dot = float(np.dot(incoming, outgoing))
    return abs(float(np.degrees(np.arctan2(cross, dot))))


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)

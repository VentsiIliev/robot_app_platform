from __future__ import annotations

import cv2
import numpy as np

from src.engine.geometry.planar import normalize_degrees, unwrap_degrees

PATH_TANGENT_HEADING_SMOOTHING_WINDOW = 5
PATH_TANGENT_LOOKAHEAD_DISTANCE_MM = 15.0
PATH_TANGENT_HEADING_DEADBAND_DEG = 5.0


def has_valid_contour(contour) -> bool:
    if contour is None:
        return False
    if isinstance(contour, np.ndarray):
        return int(contour.size) >= 3
    if isinstance(contour, list):
        return len(contour) >= 3
    return False


def canonicalize_closed_contour_points(points: np.ndarray) -> np.ndarray:
    """
    Normalize a closed contour to a stable winding and start point.

    This matters for processes that derive orientation or projected motion from
    the first contour segment. Raw captured contours often have arbitrary
    winding and arbitrary start index.
    """
    contour = np.asarray(points, dtype=np.float64)
    if contour.ndim != 2 or contour.shape[1] < 2 or len(contour) < 3:
        return contour

    contour = contour[:, :2].copy()
    if np.linalg.norm(contour[0] - contour[-1]) <= 1e-6:
        contour = contour[:-1]
    if len(contour) < 3:
        return contour

    original_contour = contour.copy()
    contour = _reorder_contour_if_discontinuous(contour)

    signed_area = 0.5 * float(
        np.dot(contour[:, 0], np.roll(contour[:, 1], -1))
        - np.dot(contour[:, 1], np.roll(contour[:, 0], -1))
    )
    # Force a consistent clockwise winding so the first segment meaning does
    # not flip between captures.
    if signed_area > 0.0:
        contour = contour[::-1].copy()

    # Use the top-most / then left-most point as a stable start index.
    start_index = int(np.lexsort((contour[:, 0], contour[:, 1]))[0])
    contour = np.roll(contour, -start_index, axis=0)
    contour = _orient_contour_like_original(contour, original_contour)

    # Return an explicitly closed contour so downstream interpolation does not
    # depend on a proximity tolerance to recover closure.
    if len(contour) >= 3 and np.linalg.norm(contour[0] - contour[-1]) > 1e-9:
        contour = np.vstack([contour, contour[:1]])
    return contour


def _reorder_contour_if_discontinuous(points: np.ndarray) -> np.ndarray:
    """
    Repair contours whose stored point order is not a continuous walk around the boundary.

    Some imported/aligned payloads preserve the right points but not the right adjacency.
    When that happens, point 0 may be correct while point 1 jumps across the workpiece.
    We detect unusually large jumps and rebuild a local nearest-neighbor loop before
    applying the usual winding/start-point canonicalization.
    """
    contour = np.asarray(points, dtype=np.float64)
    if contour.ndim != 2 or contour.shape[1] < 2 or len(contour) < 4:
        return contour

    segment_lengths = np.linalg.norm(np.diff(np.vstack([contour, contour[:1]]), axis=0), axis=1)
    positive_lengths = segment_lengths[segment_lengths > 1e-9]
    if positive_lengths.size == 0:
        return contour

    median_length = float(np.median(positive_lengths))
    if median_length <= 1e-9:
        return contour

    # If the current order is already a reasonable boundary walk, leave it alone.
    if float(np.max(positive_lengths)) <= median_length * 4.0:
        return contour

    remaining = contour.copy()
    start_index = int(np.lexsort((remaining[:, 0], remaining[:, 1]))[0])
    ordered = [remaining[start_index]]
    remaining = np.delete(remaining, start_index, axis=0)

    while len(remaining) > 0:
        current = ordered[-1]
        distances = np.linalg.norm(remaining - current, axis=1)
        next_index = int(np.argmin(distances))
        ordered.append(remaining[next_index])
        remaining = np.delete(remaining, next_index, axis=0)

    return np.asarray(ordered, dtype=np.float64)


def _orient_contour_like_original(points: np.ndarray, original_points: np.ndarray) -> np.ndarray:
    """
    Preserve the original traversal direction when possible.

    After continuity repair and start-point normalization, the remaining
    ambiguity is the loop direction. Resolve that by comparing the candidate
    second point to the original predecessor/successor around the same start.
    """
    contour = np.asarray(points, dtype=np.float64)
    original = np.asarray(original_points, dtype=np.float64)
    if len(contour) < 3 or len(original) < 3:
        return contour

    start_point = contour[0]
    original_start_index = int(np.argmin(np.linalg.norm(original - start_point, axis=1)))
    original_prev = original[(original_start_index - 1) % len(original)]
    original_next = original[(original_start_index + 1) % len(original)]

    forward_second = contour[1]
    reverse = contour[::-1].copy()
    reverse = np.roll(reverse, -np.argmin(np.linalg.norm(reverse - start_point, axis=1)), axis=0)
    reverse_second = reverse[1]

    forward_score = min(
        float(np.linalg.norm(forward_second - original_next)),
        float(np.linalg.norm(forward_second - original_prev)) * 1.25,
    )
    reverse_score = min(
        float(np.linalg.norm(reverse_second - original_next)),
        float(np.linalg.norm(reverse_second - original_prev)) * 1.25,
    )

    return reverse if reverse_score < forward_score else contour


def fast_inverse_preview_points(transformer, robot_xy_points: np.ndarray) -> np.ndarray | None:
    if robot_xy_points.size == 0:
        return np.empty((0, 2), dtype=np.float32)

    h_inv = getattr(transformer, "_H_inv", None)
    if h_inv is None:
        model = getattr(transformer, "_model", None)
        homography = getattr(model, "homography_matrix", None)
        if homography is not None:
            try:
                h_inv = np.linalg.inv(np.asarray(homography, dtype=np.float64).reshape(3, 3))
            except Exception:
                h_inv = None

    if h_inv is None:
        return None

    try:
        return cv2.perspectiveTransform(
            np.asarray(robot_xy_points, dtype=np.float32).reshape(-1, 1, 2),
            np.asarray(h_inv, dtype=np.float64),
        ).reshape(-1, 2)
    except Exception:
        return None


def compute_path_aligned_rz_degrees(
    robot_xy_points: list[tuple[float, float]],
    base_rz_offset_degrees: float = 0.0,
    lookahead_distance_mm: float = PATH_TANGENT_LOOKAHEAD_DISTANCE_MM,
    heading_deadband_deg: float = PATH_TANGENT_HEADING_DEADBAND_DEG,
) -> list[float]:
    if not robot_xy_points:
        return []
    if len(robot_xy_points) == 1:
        return [float(base_rz_offset_degrees)]
    if len(robot_xy_points) == 2:
        return [float(base_rz_offset_degrees), float(base_rz_offset_degrees)]

    segment_headings: list[float] = []
    for index in range(len(robot_xy_points) - 1):
        current = robot_xy_points[index]
        nxt = robot_xy_points[index + 1]
        dx = float(nxt[0]) - float(current[0])
        dy = float(nxt[1]) - float(current[1])
        if abs(dx) <= 1e-9 and abs(dy) <= 1e-9:
            heading_deg = segment_headings[-1] if segment_headings else 0.0
        else:
            heading_deg = float(np.degrees(np.arctan2(dy, dx)))
            if segment_headings:
                while heading_deg - segment_headings[-1] > 180.0:
                    heading_deg -= 360.0
                while heading_deg - segment_headings[-1] < -180.0:
                    heading_deg += 360.0
        segment_headings.append(heading_deg)

    if len(segment_headings) >= 3:
        window = min(PATH_TANGENT_HEADING_SMOOTHING_WINDOW, len(segment_headings))
        if window % 2 == 0:
            window -= 1
        if window >= 3:
            radius = window // 2
            padded = np.pad(np.asarray(segment_headings, dtype=float), (radius, radius), mode="edge")
            segment_headings = [float(np.mean(padded[index:index + window])) for index in range(len(segment_headings))]

    point_distances = [0.0]
    for index in range(1, len(robot_xy_points)):
        current = np.asarray(robot_xy_points[index], dtype=float)
        previous = np.asarray(robot_xy_points[index - 1], dtype=float)
        point_distances.append(point_distances[-1] + float(np.linalg.norm(current - previous)))

    lookahead_distance_mm = max(float(lookahead_distance_mm), 1.0)
    lookahead_headings: list[float] = []
    for index in range(len(segment_headings)):
        start_distance = point_distances[index]
        target_distance = start_distance + lookahead_distance_mm
        lookahead_index = index
        while lookahead_index + 1 < len(segment_headings) and point_distances[lookahead_index + 1] < target_distance:
            lookahead_index += 1
        lookahead_headings.append(float(segment_headings[lookahead_index]))

    rz_values: list[float] = [float(base_rz_offset_degrees)]
    for index in range(len(robot_xy_points) - 1):
        if index == 0:
            rz_values.append(float(base_rz_offset_degrees))
            continue
        lookahead_turn = float(lookahead_headings[index] - segment_headings[index])
        while lookahead_turn > 180.0:
            lookahead_turn -= 360.0
        while lookahead_turn < -180.0:
            lookahead_turn += 360.0
        if abs(lookahead_turn) < float(heading_deadband_deg):
            lookahead_turn = 0.0
        rz_values.append(float(base_rz_offset_degrees) + lookahead_turn)
    return rz_values[:len(robot_xy_points)]


def compute_pickup_rz_from_robot_path(
    path: list[list[float]],
    pickup_xy: tuple[float, float],
) -> float:
    if len(path) < 2:
        return 0.0
    points = np.asarray([[float(p[0]), float(p[1])] for p in path if len(p) >= 2], dtype=float)
    if len(points) < 2:
        return 0.0
    pickup_vec = np.asarray([float(pickup_xy[0]), float(pickup_xy[1])], dtype=float)
    closest_index = int(np.argmin(np.linalg.norm(points - pickup_vec, axis=1)))
    candidate_pairs: list[tuple[int, int]] = []
    if closest_index > 0:
        candidate_pairs.append((closest_index - 1, closest_index))
    if closest_index + 1 < len(points):
        candidate_pairs.append((closest_index, closest_index + 1))
    if closest_index > 0 and closest_index + 1 < len(points):
        candidate_pairs.append((closest_index - 1, closest_index + 1))
    dx = dy = 0.0
    for start_idx, end_idx in candidate_pairs:
        segment = points[end_idx] - points[start_idx]
        seg_len = float(np.linalg.norm(segment))
        if seg_len > 1e-6:
            dx = float(segment[0])
            dy = float(segment[1])
            break
    if abs(dx) <= 1e-9 and abs(dy) <= 1e-9:
        return 0.0
    heading_from_x_deg = float(np.degrees(np.arctan2(dy, dx)))
    return normalize_degrees(heading_from_x_deg)


def _first_directed_heading_from_x(path: list[list[float]]) -> float | None:
    if len(path) < 2:
        return None
    points = np.asarray([[float(p[0]), float(p[1])] for p in path if len(p) >= 2], dtype=float)
    if len(points) < 2:
        return None
    for index in range(len(points) - 1):
        segment = points[index + 1] - points[index]
        seg_len = float(np.linalg.norm(segment))
        if seg_len > 1e-6:
            dx = float(segment[0])
            dy = float(segment[1])
            heading_from_x_deg = float(np.degrees(np.arctan2(dy, dx)))
            return normalize_degrees(heading_from_x_deg)
    return None


def compute_pickup_rz_from_robot_contour(points: list[list[float]] | np.ndarray) -> float:
    """
    Estimate pickup orientation from contour central moments instead of a local tangent.

    This is better for centroid pickup on closed workpiece contours, because the
    centroid is inside the shape and does not have a meaningful boundary tangent.
    """
    contour = np.asarray(points, dtype=float)
    if contour.ndim != 2 or contour.shape[1] < 2 or len(contour) < 2:
        return 0.0
    contour = contour[:, :2]
    if len(contour) < 3:
        return 0.0

    moments = cv2.moments(contour.astype(np.float32).reshape(-1, 1, 2))
    mu20 = float(moments.get("mu20", 0.0))
    mu11 = float(moments.get("mu11", 0.0))
    mu02 = float(moments.get("mu02", 0.0))

    if abs(mu20) < 1e-10 and abs(mu11) < 1e-10 and abs(mu02) < 1e-10:
        return 0.0

    heading_from_x_deg = float(np.degrees(0.5 * np.arctan2(2.0 * mu11, mu20 - mu02)))
    return normalize_degrees(heading_from_x_deg)


def compute_pickup_rz_from_robot_contour_with_direction(
    contour_points: list[list[float]] | np.ndarray,
    path_points: list[list[float]] | np.ndarray,
) -> float:
    """
    Estimate pickup orientation from the whole contour, then resolve the 180-degree
    ambiguity using the directed execution path ordering.
    """
    contour_rz = compute_pickup_rz_from_robot_contour(contour_points)
    path_heading_rz = _first_directed_heading_from_x(
        [list(p) for p in np.asarray(path_points, dtype=float)]
    )
    if path_heading_rz is None:
        return contour_rz

    alternate_rz = normalize_degrees(contour_rz + 180.0)
    if abs(unwrap_degrees(path_heading_rz, contour_rz) - path_heading_rz) <= abs(
        unwrap_degrees(path_heading_rz, alternate_rz) - path_heading_rz
    ):
        return contour_rz
    return alternate_rz


def rebuild_pose_path_from_xy(
    xy_points: np.ndarray,
    prototype_path: list[list[float]],
    rz_mode: str,
    tangent_lookahead_distance_mm: float = PATH_TANGENT_LOOKAHEAD_DISTANCE_MM,
    tangent_heading_deadband_deg: float = PATH_TANGENT_HEADING_DEADBAND_DEG,
) -> list[list[float]]:
    if len(xy_points) == 0 or not prototype_path:
        return []
    first_pose = prototype_path[0]
    base_z = float(first_pose[2]) if len(first_pose) >= 3 else 0.0
    rx = float(first_pose[3]) if len(first_pose) >= 4 else 180.0
    ry = float(first_pose[4]) if len(first_pose) >= 5 else 0.0
    base_rz = float(first_pose[5]) if len(first_pose) >= 6 else 0.0
    robot_xy_points = [(float(point[0]), float(point[1])) for point in xy_points]
    if str(rz_mode or "constant").strip().lower() == "path_tangent":
        rz_values = compute_path_aligned_rz_degrees(
            robot_xy_points,
            base_rz_offset_degrees=base_rz,
            lookahead_distance_mm=tangent_lookahead_distance_mm,
            heading_deadband_deg=tangent_heading_deadband_deg,
        )
    else:
        rz_values = [base_rz for _ in robot_xy_points]
    return [[float(x), float(y), base_z, rx, ry, float(rz)] for (x, y), rz in zip(robot_xy_points, rz_values)]

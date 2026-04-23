from __future__ import annotations

import cv2
import numpy as np

from src.engine.geometry.planar import normalize_degrees

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
    heading_relative_to_y_deg = heading_from_x_deg - 90.0
    return normalize_degrees(heading_relative_to_y_deg)


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

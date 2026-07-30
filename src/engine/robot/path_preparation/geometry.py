from __future__ import annotations

import cv2
import numpy as np
import logging
from src.engine.geometry.planar import nearest_axis_equivalent_degrees, normalize_degrees, unwrap_degrees

PATH_TANGENT_HEADING_SMOOTHING_WINDOW = 5
PATH_TANGENT_LOOKAHEAD_DISTANCE_MM = 15.0
PATH_TANGENT_HEADING_DEADBAND_DEG = 5.0

_logger = logging.getLogger(__name__)

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

    Important: canonicalization must not invent new boundary adjacency. If the
    raw contour order is already a valid closed walk, only cyclic shift and
    optional reversal are allowed. Rebuilding the loop with nearest-neighbor
    logic can create broken shapes for otherwise valid captures.
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

    signed_area = 0.5 * float(
        np.dot(contour[:, 0], np.roll(contour[:, 1], -1))
        - np.dot(contour[:, 1], np.roll(contour[:, 0], -1))
    )
    # Force a consistent clockwise winding so the first segment meaning does
    # not flip between captures.
    if signed_area > 0.0:
        contour = contour[::-1].copy()

    # Use the top-most / then left-most point as a stable start index while
    # preserving original adjacency.
    start_index = int(np.lexsort((contour[:, 0], contour[:, 1]))[0])
    contour = np.roll(contour, -start_index, axis=0)
    contour = _orient_contour_like_original(contour, original_contour)

    # Return an explicitly closed contour so downstream interpolation does not
    # depend on a proximity tolerance to recover closure.
    if len(contour) >= 3 and np.linalg.norm(contour[0] - contour[-1]) > 1e-9:
        contour = np.vstack([contour, contour[:1]])
    return contour


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
    boundary_xy_points: np.ndarray | None = None,
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

    boundary_indices: set[int] = set()
    if boundary_xy_points is not None:
        try:
            boundary_xy = np.asarray(boundary_xy_points, dtype=float).reshape(-1, 2)
        except (TypeError, ValueError):
            boundary_xy = np.empty((0, 2), dtype=float)
        for index, point in enumerate(robot_xy_points):
            if len(boundary_xy) and bool(np.any(np.linalg.norm(boundary_xy - np.asarray(point, dtype=float), axis=1) <= 1e-6)):
                boundary_indices.add(index)

    if len(segment_headings) >= 3 and boundary_indices:
        smoothed_headings = list(segment_headings)
        split_points = sorted(index for index in boundary_indices if 0 < index < len(segment_headings))
        span_starts = [0, *split_points]
        span_ends = [index - 1 for index in split_points]
        span_ends.append(len(segment_headings) - 1)
        for start, end in zip(span_starts, span_ends):
            span = segment_headings[start:end + 1]
            if len(span) < 3:
                continue
            window = min(PATH_TANGENT_HEADING_SMOOTHING_WINDOW, len(span))
            if window % 2 == 0:
                window -= 1
            if window < 3:
                continue
            radius = window // 2
            padded = np.pad(np.asarray(span, dtype=float), (radius, radius), mode="edge")
            for offset in range(len(span)):
                smoothed_headings[start + offset] = float(np.mean(padded[offset:offset + window]))
        segment_headings = smoothed_headings

    if len(segment_headings) >= 3 and not boundary_indices:
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
            if lookahead_index + 1 in boundary_indices and lookahead_index + 1 != index:
                break
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


def compute_pickup_rz_from_stable_paint_segment(
    path: list[list[float]] | np.ndarray,
    reference_rz: float = 0.0,
) -> float:
    """
    Select a pickup orientation from a stable segment of the prepared paint path.

    Closed workpiece contours do not always have a useful whole-shape axis:
    asymmetry can pull moment/PCA orientation away from the edge frame that will
    be painted. This selector instead scans the final execution contour and
    favors segments that are locally straight and require the smallest
    axis-equivalent rotation from the pickup reference orientation.
    """
    points = np.asarray(path, dtype=float)
    if points.ndim != 2 or points.shape[1] < 2 or len(points) < 2:
        return 0.0
    points = points[:, :2]

    vectors = points[1:] - points[:-1]
    lengths = np.linalg.norm(vectors, axis=1)
    valid_indices = [int(index) for index, length in enumerate(lengths) if float(length) > 1e-6]
    if not valid_indices:
        return 0.0

    headings = np.asarray(
        [
            normalize_degrees(float(np.degrees(np.arctan2(vector[1], vector[0]))))
            if float(lengths[index]) > 1e-6 else 0.0
            for index, vector in enumerate(vectors)
        ],
        dtype=float,
    )

    reference = float(reference_rz)
    best_index = valid_indices[0]
    best_key: tuple[float, float, float, int] | None = None
    window = 5

    for index in valid_indices:
        heading = float(headings[index])
        selected_heading = nearest_axis_equivalent_degrees(reference, heading)
        rotation_cost = abs(unwrap_degrees(reference, selected_heading) - reference)

        neighbor_errors: list[float] = []
        straight_run_length = float(lengths[index])
        for neighbor in range(max(0, index - window), min(len(headings), index + window + 1)):
            if neighbor == index or float(lengths[neighbor]) <= 1e-6:
                continue
            error = abs(unwrap_degrees(heading, float(headings[neighbor])) - heading)
            neighbor_errors.append(error)
            if error <= 5.0:
                straight_run_length += float(lengths[neighbor])

        straightness_cost = float(np.mean(neighbor_errors)) if neighbor_errors else 0.0
        straight_bonus = -min(straight_run_length, 25.0)
        key = (rotation_cost, straightness_cost, straight_bonus, index)
        if best_key is None or key < best_key:
            best_key = key
            best_index = index

    return nearest_axis_equivalent_degrees(reference, float(headings[best_index]))


def compute_pickup_rz_from_initial_paint_segment(
    path: list[list[float]] | np.ndarray,
    reference_rz: float = 0.0,
    *,
    max_run_mm: float = 25.0,
    heading_tolerance_deg: float = 5.0,
) -> float:
    """Return pickup RZ from the first stable run of the prepared paint path.

    The workpiece is picked before the paint handoff. To align the selected
    start of the contour with the paint axis, pickup RZ must follow the initial
    directed segment instead of whichever later segment happens to be closest
    to zero rotation.
    """
    points = np.asarray(path, dtype=float)
    if points.ndim != 2 or points.shape[1] < 2 or len(points) < 2:
        return 0.0
    points = points[:, :2]

    vectors = points[1:] - points[:-1]
    lengths = np.linalg.norm(vectors, axis=1)
    valid_indices = [int(index) for index, length in enumerate(lengths) if float(length) > 1e-6]
    if not valid_indices:
        return 0.0

    first_index = valid_indices[0]
    first_heading = normalize_degrees(
        float(np.degrees(np.arctan2(vectors[first_index][1], vectors[first_index][0])))
    )
    run_vector = np.zeros(2, dtype=float)
    run_length = 0.0
    max_run_mm = max(0.0, float(max_run_mm))
    heading_tolerance_deg = max(0.0, float(heading_tolerance_deg))

    for index in valid_indices:
        heading = normalize_degrees(
            float(np.degrees(np.arctan2(vectors[index][1], vectors[index][0])))
        )
        heading_error = abs(unwrap_degrees(first_heading, heading) - first_heading)
        if index != first_index and heading_error > heading_tolerance_deg:
            break
        run_vector += vectors[index]
        run_length += float(lengths[index])
        if max_run_mm > 0.0 and run_length >= max_run_mm:
            break

    if float(np.linalg.norm(run_vector)) <= 1e-9:
        selected_heading = first_heading
    else:
        selected_heading = normalize_degrees(
            float(np.degrees(np.arctan2(run_vector[1], run_vector[0])))
        )
    return unwrap_degrees(float(reference_rz), selected_heading)


def compute_pickup_rz_from_min_rect_long_axis(
    points: list[list[float]] | np.ndarray,
    reference_rz: float = 0.0,
) -> float:
    """Return pickup RZ from the long axis of the contour minimum-area rectangle."""
    contour = np.asarray(points, dtype=float)
    if contour.ndim != 2 or contour.shape[1] < 2 or len(contour) < 2:
        return 0.0
    contour = contour[:, :2]
    if len(contour) < 3:
        return 0.0

    rect = cv2.minAreaRect(contour.astype(np.float32).reshape(-1, 1, 2))
    box = cv2.boxPoints(rect).astype(float)
    if len(box) < 4:
        return 0.0

    best_vector: np.ndarray | None = None
    best_length = 0.0
    for index in range(4):
        vector = box[(index + 1) % 4] - box[index]
        length = float(np.linalg.norm(vector))
        if length > best_length:
            best_length = length
            best_vector = vector

    if best_vector is None or best_length <= 1e-9:
        return 0.0

    heading = normalize_degrees(
        float(np.degrees(np.arctan2(float(best_vector[1]), float(best_vector[0]))))
    )
    return nearest_axis_equivalent_degrees(float(reference_rz), heading)


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
    _logger.debug(f"compute_pickup_rz_from_robot_contour_with_direction: {contour_rz}")
    path_heading_rz = _first_directed_heading_from_x(
        [list(p) for p in np.asarray(path_points, dtype=float)]
    )
    if path_heading_rz is None:
        return contour_rz

    alternate_rz = normalize_degrees(contour_rz + 180.0)
    _logger.debug(f"alternate_rz: {alternate_rz}")

    if abs(unwrap_degrees(path_heading_rz, contour_rz) - path_heading_rz) <= abs(
        unwrap_degrees(path_heading_rz, alternate_rz) - path_heading_rz
    ):
        _logger.debug(f"Returning raw rz: {contour_rz}")
        return contour_rz

    _logger.debug(f"Redurning alternate rz: {alternate_rz}")
    return alternate_rz


def rebuild_pose_path_from_xy(
    xy_points: np.ndarray,
    prototype_path: list[list[float]],
    rz_mode: str,
    tangent_lookahead_distance_mm: float = PATH_TANGENT_LOOKAHEAD_DISTANCE_MM,
    tangent_heading_deadband_deg: float = PATH_TANGENT_HEADING_DEADBAND_DEG,
    tangent_boundary_xy: np.ndarray | None = None,
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
            boundary_xy_points=tangent_boundary_xy,
        )
    else:
        rz_values = [base_rz for _ in robot_xy_points]
    return [[float(x), float(y), base_z, rx, ry, float(rz)] for (x, y), rz in zip(robot_xy_points, rz_values)]

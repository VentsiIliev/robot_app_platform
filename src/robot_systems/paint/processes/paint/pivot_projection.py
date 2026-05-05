import numpy as np

from src.engine.geometry.planar import normalize_degrees, rotate_xy_about, unwrap_degrees
from src.robot_systems.paint.processes.paint.config import (
    PaintSimulationConfig,
    _PAINT_ROTATION_DEADBAND_DEG,
    _PAINT_SMOOTH_MAX_ANGULAR_STEP_DEG,
    _PAINT_SMOOTH_MAX_LINEAR_STEP_MM,
)


def rebase_projected_paint_path_to_zero_start_rz(
    path: list[list[float]],
    config: PaintSimulationConfig,
) -> list[list[float]]:
    """Shift a projected paint path so its active rotation component starts at zero."""
    if not path:
        return []
    rebased = [list(pose) for pose in path]
    rotation_index = config.rotation_index
    start_rz = float(rebased[0][rotation_index]) if len(rebased[0]) > rotation_index else 0.0
    for pose in rebased:
        if len(pose) > rotation_index:
            pose[rotation_index] = unwrap_degrees(0.0, float(pose[rotation_index]) - start_rz)
    return rebased


def project_paint_motion_geometry(
    path: list[list[float]],
    pivot_pose: list[float],
    config: PaintSimulationConfig,
) -> tuple[list[list[float]], list[np.ndarray], list[dict[str, float | int]]]:
    """Project a source paint path into pickup/pivot motion geometry around the configured base pose."""
    if not path:
        return [], [], []
    planar_i, planar_j = config.planar_coordinate_indices
    source_planar_i, source_planar_j = config.source_planar_coordinate_indices
    orthogonal_index = config.orthogonal_position_index
    rotation_index = config.rotation_index
    if len(path) == 1:
        point = path[0]
        planar_point = np.array([[float(point[source_planar_i]), float(point[source_planar_j])]], dtype=float)
        return [list(point)], [planar_point], []

    pivot_x = float(pivot_pose[planar_i])
    pivot_y = float(pivot_pose[planar_j])
    pivot_orthogonal = (
        float(pivot_pose[orthogonal_index])
        if len(pivot_pose) > orthogonal_index else float(path[0][orthogonal_index])
    )
    rx = float(pivot_pose[3]) if len(pivot_pose) >= 4 else float(path[0][3])
    ry = float(pivot_pose[4]) if len(pivot_pose) >= 5 else float(path[0][4])
    rz = float(pivot_pose[5]) if len(pivot_pose) >= 6 else float(path[0][5])
    orientation_overrides = config.orientation_overrides_deg
    rx = float(orientation_overrides.get("rx", rx))
    ry = float(orientation_overrides.get("ry", ry))
    rz = float(orientation_overrides.get("rz", rz))
    base_rz = (
        float(pivot_pose[rotation_index])
        if len(pivot_pose) > rotation_index else float(path[0][rotation_index])
    )
    # Translation axis and pivot side are separate concepts.
    # The axis heading defines travel along the pivot.
    # `paint_side` only chooses which normal-side of that axis the workpiece
    # should occupy after alignment.
    paint_axis_heading = normalize_degrees(base_rz + config.paint_axis_offset_deg)
    translation_heading = float(paint_axis_heading)
    if config.direction_sign < 0:
        translation_heading = normalize_degrees(translation_heading + 180.0)
    contact_segment_heading = normalize_degrees(
        translation_heading + config.contact_heading_offset_deg
    )

    points = np.array(
        [[float(point[source_planar_i]), float(point[source_planar_j])] for point in path],
        dtype=float,
    )
    if len(points) < 2:
        return (
            [
                _compose_pose(
                    reference_pose=path[0],
                    planar_i=planar_i,
                    planar_j=planar_j,
                    planar_a=float(points[0][0]),
                    planar_b=float(points[0][1]),
                    orthogonal_index=orthogonal_index,
                    orthogonal_value=pivot_orthogonal,
                    rotation_index=rotation_index,
                    rotation_value=base_rz,
                    rx=rx,
                    ry=ry,
                    rz=rz,
                )
            ],
            [points.copy()],
            [{
                "index": 0,
                "segment_length": 0.0,
                "segment_heading": 0.0,
                "rotation_delta_raw": 0.0,
                "rotation_delta_applied": 0.0,
                "current_rz": base_rz,
            }],
        )

    def _centroid_xy(current_points: np.ndarray) -> tuple[float, float]:
        return (float(np.mean(current_points[:, 0])), float(np.mean(current_points[:, 1])))

    def _rotate_shape(current_points: np.ndarray, angle_deg: float, pivot_xy: tuple[float, float]) -> np.ndarray:
        return np.array(
            [rotate_xy_about((float(point[0]), float(point[1])), angle_deg, pivot_xy) for point in current_points],
            dtype=float,
        )

    def _segment_heading_deg(point_a: np.ndarray, point_b: np.ndarray) -> float:
        dx = float(point_b[0] - point_a[0])
        dy = float(point_b[1] - point_a[1])
        return float(np.degrees(np.arctan2(dy, dx)))

    pivot_xy = (pivot_x, pivot_y)
    points = _canonicalize_closed_source_path(
        points,
        pivot_xy=pivot_xy,
        translation_heading=translation_heading,
        contact_segment_heading=contact_segment_heading,
        side_sign=config.side_sign,
    )

    # First, orient the source shape so its first segment points along the
    # configured paint axis. This defines the starting pickup orientation.
    initial_heading = _segment_heading_deg(points[0], points[1])
    initial_rotation = unwrap_degrees(0.0, contact_segment_heading - initial_heading)
    points = _rotate_shape(points, initial_rotation, (float(points[0][0]), float(points[0][1])))

    # Then translate the rotated shape so its first point sits exactly on the
    # physical pivot/base position used by the robot.
    translate_to_pivot = np.array([pivot_x - float(points[0][0]), pivot_y - float(points[0][1])], dtype=float)
    points = points + translate_to_pivot

    current_rz = unwrap_degrees(base_rz, base_rz + initial_rotation)
    result: list[list[float]] = []
    snapshots: list[np.ndarray] = []
    diagnostics: list[dict[str, float | int]] = []
    center_xy = _centroid_xy(points)
    result.append(
        _compose_pose(
            reference_pose=path[0],
            planar_i=planar_i,
            planar_j=planar_j,
            planar_a=center_xy[0],
            planar_b=center_xy[1],
            orthogonal_index=orthogonal_index,
            orthogonal_value=pivot_orthogonal,
            rotation_index=rotation_index,
            rotation_value=current_rz,
            rx=rx,
            ry=ry,
            rz=rz,
        )
    )
    snapshots.append(points.copy())
    diagnostics.append(
        {
            "index": 0,
            "segment_length": 0.0,
            "segment_heading": initial_heading,
            "rotation_delta_raw": initial_rotation,
            "rotation_delta_applied": initial_rotation,
            "current_rz": current_rz,
        }
    )

    axis_vector = np.array(
        [
            float(np.cos(np.radians(paint_axis_heading))),
            float(np.sin(np.radians(paint_axis_heading))),
        ],
        dtype=float,
    )

    for index in range(len(points) - 1):
        current_point = points[index]
        next_point = points[index + 1]
        segment_length = float(np.linalg.norm(next_point - current_point))
        if segment_length <= 1e-9:
            center_xy = _centroid_xy(points)
            result.append(
                _compose_pose(
                    reference_pose=path[min(index + 1, len(path) - 1)],
                    planar_i=planar_i,
                    planar_j=planar_j,
                    planar_a=center_xy[0],
                    planar_b=center_xy[1],
                    orthogonal_index=orthogonal_index,
                    orthogonal_value=pivot_orthogonal,
                    rotation_index=rotation_index,
                    rotation_value=current_rz,
                    rx=rx,
                    ry=ry,
                    rz=rz,
                )
            )
            snapshots.append(points.copy())
            diagnostics.append(
                {
                    "index": index + 1,
                    "segment_length": 0.0,
                    "segment_heading": 0.0,
                    "rotation_delta_raw": 0.0,
                    "rotation_delta_applied": 0.0,
                    "current_rz": current_rz,
                }
            )
            continue

        # Compare the current projected segment heading to the desired paint
        # axis. The delta becomes the robot/tool rotation needed before the next
        # projected translation step.
        segment_heading = _segment_heading_deg(current_point, next_point)
        rotation_delta_raw = unwrap_degrees(0.0, contact_segment_heading - segment_heading)
        rotation_delta = rotation_delta_raw

        # Ignore tiny heading noise to avoid jittering the projected RZ.
        if abs(rotation_delta) < _PAINT_ROTATION_DEADBAND_DEG:
            rotation_delta = 0.0
        if abs(rotation_delta) > 1e-9:
            # Rotate the whole shape around the fixed pivot, because the
            # workpiece is assumed to swing around that base point.
            points = _rotate_shape(points, rotation_delta, pivot_xy)
            current_rz = unwrap_degrees(current_rz, current_rz + rotation_delta)

        # After any rotation, advance the entire shape along the configured
        # translation axis by the original segment length. This is the key
        # "projected motion" assumption: source path arc length becomes linear
        # travel of the whole workpiece along the pivot axis.
        points = points + axis_vector * segment_length * config.direction_sign
        center_xy = _centroid_xy(points)
        result.append(
            _compose_pose(
                reference_pose=path[min(index + 1, len(path) - 1)],
                planar_i=planar_i,
                planar_j=planar_j,
                planar_a=center_xy[0],
                planar_b=center_xy[1],
                orthogonal_index=orthogonal_index,
                orthogonal_value=pivot_orthogonal,
                rotation_index=rotation_index,
                rotation_value=current_rz,
                rx=rx,
                ry=ry,
                rz=rz,
            )
        )
        snapshots.append(points.copy())
        diagnostics.append(
            {
                "index": index + 1,
                "segment_length": segment_length,
                "segment_heading": segment_heading,
                "rotation_delta_raw": rotation_delta_raw,
                "rotation_delta_applied": rotation_delta,
                "current_rz": current_rz,
            }
        )

    result = result[:len(path)]
    snapshots = snapshots[:len(path)]
    diagnostics = diagnostics[:len(path)]
    return result, snapshots, diagnostics


def _compose_pose(
    *,
    reference_pose: list[float],
    planar_i: int,
    planar_j: int,
    planar_a: float,
    planar_b: float,
    orthogonal_index: int,
    orthogonal_value: float,
    rotation_index: int,
    rotation_value: float,
    rx: float,
    ry: float,
    rz: float,
) -> list[float]:
    """Build a full 6D pose from a projected 2D point and the active motion plane."""
    pose = [float(value) for value in reference_pose[:6]]
    while len(pose) < 6:
        pose.append(0.0)
    pose[3] = float(rx)
    pose[4] = float(ry)
    pose[5] = float(rz)
    pose[planar_i] = float(planar_a)
    pose[planar_j] = float(planar_b)
    pose[orthogonal_index] = float(orthogonal_value)
    pose[rotation_index] = float(rotation_value)
    return pose


def _segment_heading_deg(point_a: np.ndarray, point_b: np.ndarray) -> float:
    dx = float(point_b[0] - point_a[0])
    dy = float(point_b[1] - point_a[1])
    return float(np.degrees(np.arctan2(dy, dx)))


def _angle_error_deg(a: float, b: float) -> float:
    return abs(unwrap_degrees(float(b), float(a)) - float(b))


def _canonicalize_closed_source_path(
    points: np.ndarray,
    *,
    pivot_xy: tuple[float, float],
    translation_heading: float,
    contact_segment_heading: float,
    side_sign: float,
) -> np.ndarray:
    """
    Give closed contours a pivot-aware start point and traversal direction.

    The first point should be the boundary point that is closest to the actual
    pivot location, then the loop direction should be chosen to match the
    requested projected travel direction.
    """
    contour = np.asarray(points, dtype=float)
    if len(contour) < 3:
        return contour

    is_closed = float(np.linalg.norm(contour[0] - contour[-1])) <= 1e-6
    if is_closed:
        contour = contour[:-1]
    if len(contour) < 3:
        return points

    pivot_vec = np.asarray([float(pivot_xy[0]), float(pivot_xy[1])], dtype=float)
    start_index = int(np.argmin(np.linalg.norm(contour - pivot_vec, axis=1)))

    desired_heading = float(contact_segment_heading)
    desired_side_sign = 1.0 if float(side_sign) >= 0.0 else -1.0

    forward = np.roll(contour, -start_index, axis=0)
    reverse = forward[::-1].copy()
    reverse = np.roll(reverse, -np.argmin(np.linalg.norm(reverse - forward[0], axis=1)), axis=0)
    candidates = [forward, reverse]

    def _preview_aligned(candidate: np.ndarray) -> tuple[np.ndarray, float, float]:
        heading = _segment_heading_deg(candidate[0], candidate[1])
        rotation = unwrap_degrees(0.0, desired_heading - heading)
        rotated = np.array(
            [rotate_xy_about((float(point[0]), float(point[1])), rotation, (float(candidate[0][0]), float(candidate[0][1]))) for point in candidate],
            dtype=float,
        )
        translated = rotated + (pivot_vec - rotated[0])
        return translated, heading, rotation

    def _side_score(aligned: np.ndarray) -> float:
        axis_vector = np.asarray(
            [
                float(np.cos(np.radians(translation_heading))),
                float(np.sin(np.radians(translation_heading))),
            ],
            dtype=float,
        )
        normal = np.asarray([-axis_vector[1], axis_vector[0]], dtype=float)
        relative = aligned[1:] - pivot_vec if len(aligned) > 1 else aligned - pivot_vec
        if len(relative) == 0:
            return 0.0
        return float(np.mean(relative @ normal))

    best_ordered = forward
    best_key: tuple[float, float] | None = None
    for candidate in candidates:
        aligned_preview, heading, _ = _preview_aligned(candidate)
        heading_error = _angle_error_deg(heading, desired_heading)
        side_score = _side_score(aligned_preview)
        side_penalty = 0.0 if side_score * desired_side_sign >= 0.0 else 1.0
        key = (side_penalty, heading_error)
        if best_key is None or key < best_key:
            best_key = key
            best_ordered = candidate

    return np.vstack([best_ordered, best_ordered[:1]])


def _compute_pickup_rz_from_path(
    path: list[list[float]],
    pickup_xy: tuple[float, float],
) -> float:
    """Estimate pickup orientation from the local path tangent nearest the pickup point."""
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

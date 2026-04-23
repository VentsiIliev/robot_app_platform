import numpy as np

from src.engine.geometry.planar import normalize_degrees, rotate_xy_about, unwrap_degrees
from src.robot_systems.paint.processes.paint.config import (
    PivotSimulationConfig,
    _PIVOT_ROTATION_DEADBAND_DEG,
    _PIVOT_SMOOTH_MAX_ANGULAR_STEP_DEG,
    _PIVOT_SMOOTH_MAX_LINEAR_STEP_MM,
)


def rebase_projected_pivot_path_to_zero_start_rz(path: list[list[float]]) -> list[list[float]]:
    """Shift a projected pivot path so its first pose starts at RZ zero."""
    if not path:
        return []
    rebased = [list(pose) for pose in path]
    start_rz = float(rebased[0][5]) if len(rebased[0]) >= 6 else 0.0
    for pose in rebased:
        if len(pose) >= 6:
            pose[5] = unwrap_degrees(0.0, float(pose[5]) - start_rz)
    return rebased


def project_pivot_motion_geometry(
    path: list[list[float]],
    pivot_pose: list[float],
    config: PivotSimulationConfig,
) -> tuple[list[list[float]], list[np.ndarray], list[dict[str, float | int]]]:
    """Project a source paint path into pickup/pivot motion geometry around the configured base pose."""
    if not path:
        return [], [], []
    if len(path) == 1:
        return [list(path[0])], [np.array([[float(path[0][0]), float(path[0][1])]], dtype=float)], []

    pivot_x = float(pivot_pose[0])
    pivot_y = float(pivot_pose[1])
    pivot_z = float(pivot_pose[2]) if len(pivot_pose) >= 3 else float(path[0][2])
    rx = float(pivot_pose[3]) if len(pivot_pose) >= 4 else float(path[0][3])
    ry = float(pivot_pose[4]) if len(pivot_pose) >= 5 else float(path[0][4])
    base_rz = float(pivot_pose[5]) if len(pivot_pose) >= 6 else float(path[0][5])
    paint_axis_heading = base_rz + config.paint_axis_offset_deg

    points = np.array([[float(point[0]), float(point[1])] for point in path], dtype=float)
    if len(points) < 2:
        return (
            [[float(points[0][0]), float(points[0][1]), pivot_z, rx, ry, base_rz]],
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

    # First, orient the source shape so its first segment points along the
    # configured paint axis. This defines the starting pickup orientation.
    initial_heading = _segment_heading_deg(points[0], points[1])
    initial_rotation = unwrap_degrees(0.0, paint_axis_heading - initial_heading)
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
    result.append([center_xy[0], center_xy[1], pivot_z, rx, ry, current_rz])
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
            result.append([center_xy[0], center_xy[1], pivot_z, rx, ry, current_rz])
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
        rotation_delta_raw = unwrap_degrees(0.0, paint_axis_heading - segment_heading)
        rotation_delta = rotation_delta_raw

        # Ignore tiny heading noise to avoid jittering the projected RZ.
        if abs(rotation_delta) < _PIVOT_ROTATION_DEADBAND_DEG:
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
        points = points + axis_vector * segment_length * config.side_sign * config.direction_sign
        center_xy = _centroid_xy(points)
        result.append([center_xy[0], center_xy[1], pivot_z, rx, ry, current_rz])
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
#
#
# def _densify_pose_path(
#     poses: list[list[float]],
#     max_linear_step_mm: float = _PIVOT_SMOOTH_MAX_LINEAR_STEP_MM,
#     max_angular_step_deg: float = _PIVOT_SMOOTH_MAX_ANGULAR_STEP_DEG,
# ) -> list[list[float]]:
#     """Insert intermediate poses so projected pivot motion respects linear and angular step limits."""
#     if len(poses) < 2:
#         return [list(pose) for pose in poses]
#
#     densified: list[list[float]] = [list(poses[0])]
#     max_linear_step_mm = max(float(max_linear_step_mm), 1e-3)
#     max_angular_step_deg = max(float(max_angular_step_deg), 1e-3)
#
#     for target_pose in poses[1:]:
#         start_pose = densified[-1]
#         end_pose = list(target_pose)
#         dx = float(end_pose[0]) - float(start_pose[0])
#         dy = float(end_pose[1]) - float(start_pose[1])
#         dz = float(end_pose[2]) - float(start_pose[2])
#         linear_distance = float(np.sqrt(dx * dx + dy * dy + dz * dz))
#         angular_delta = abs(unwrap_degrees(float(start_pose[5]), float(end_pose[5])) - float(start_pose[5]))
#         steps = max(1, int(np.ceil(max(
#             linear_distance / max_linear_step_mm,
#             angular_delta / max_angular_step_deg,
#         ))))
#
#         previous_rz = float(start_pose[5])
#         target_rz = unwrap_degrees(previous_rz, float(end_pose[5]))
#         for step_index in range(1, steps + 1):
#             ratio = step_index / steps
#             interpolated = [
#                 float(start_pose[0]) + dx * ratio,
#                 float(start_pose[1]) + dy * ratio,
#                 float(start_pose[2]) + dz * ratio,
#                 float(start_pose[3]) + (float(end_pose[3]) - float(start_pose[3])) * ratio,
#                 float(start_pose[4]) + (float(end_pose[4]) - float(start_pose[4])) * ratio,
#                 previous_rz + (target_rz - previous_rz) * ratio,
#             ]
#             densified.append(interpolated)
#
#     return densified

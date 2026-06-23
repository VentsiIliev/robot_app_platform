"""Paint pivot projection helpers.

This module converts a prepared workpiece contour into robot poses that keep a
chosen contour/contact point on the physical paint pivot. The calculation is
done in the active 2D motion plane from ``PaintSimulationConfig``:

* ``xy_z_rz`` uses X/Y as the contact plane and RZ as the active rotation.
* ``xz_y_ry`` uses X/Z as the contact plane and RY as the active rotation.

The returned poses describe the projected selected-tool/workpiece anchor. The
executor can later convert those projected tool poses into robot TCP commands
when TCP and tool point are not the same physical point. The snapshot arrays are
the simulated workpiece contour after each projection step, and diagnostics are
small numeric breadcrumbs for debug plots/logs.
"""

import numpy as np

from src.engine.geometry.planar import normalize_degrees, rotate_xy_about, unwrap_degrees
from src.robot_systems.paint.processes.paint.config import (
    PAINT_PROJECTION_TUNING,
    PaintSimulationConfig,
)
import logging
_logger = logging.getLogger("Core")


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



def project_paint_motion_geometry_continuous(
    path: list[list[float]],
    pivot_pose: list[float],
    config: PaintSimulationConfig,
    anchor_xy: tuple[float, float] | None = None,
    source_rotation_deg: float = 0.0,
) -> tuple[list[list[float]], list[np.ndarray], list[dict[str, float | int]]]:
    """Project a dense contour with an incremental RTCP workpiece transform.

    The input path is expected to be the final pivot source contour, already
    resampled to roughly 1 mm spacing by the executor. The algorithm mirrors the
    legacy KAREL RTCP loop: the current contour point is the pivot contact,
    the remaining workpiece is rotated around that point, then translated along
    the contact axis so the next contour point becomes the new pivot contact.
    The geometry rotation is kept separate from the robot command rotation sign.
    """
    if not path:
        return [], [], []

    planar_i, planar_j = config.planar_coordinate_indices
    source_planar_i, source_planar_j = config.source_planar_coordinate_indices
    orthogonal_index = config.orthogonal_position_index
    rotation_index = config.rotation_index

    pivot_x = float(pivot_pose[planar_i])
    pivot_y = float(pivot_pose[planar_j])
    pivot_xy = (pivot_x, pivot_y)
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

    points = np.array(
        [[float(point[source_planar_i]), float(point[source_planar_j])] for point in path],
        dtype=float,
    )
    if len(points) == 0:
        return [], [], []

    tool_anchor = (
        np.asarray([float(anchor_xy[0]), float(anchor_xy[1])], dtype=float)
        if anchor_xy is not None else np.asarray([float(np.mean(points[:, 0])), float(np.mean(points[:, 1]))], dtype=float)
    )

    source_rotation = float(source_rotation_deg or 0.0)
    if abs(source_rotation) > 1e-9:
        rotation_anchor = tool_anchor.copy()
        points = np.array(
            [
                rotate_xy_about(
                    (float(point[0]), float(point[1])),
                    source_rotation,
                    (float(rotation_anchor[0]), float(rotation_anchor[1])),
                )
                for point in points
            ],
            dtype=float,
        )

    paint_axis_heading = normalize_degrees(base_rz + config.paint_axis_offset_deg)
    translation_heading = float(paint_axis_heading)
    if config.direction_sign < 0:
        translation_heading = normalize_degrees(translation_heading + 180.0)
    contact_segment_heading = normalize_degrees(
        translation_heading + config.contact_heading_offset_deg
    )

    is_closed_path = (
        len(points) >= 3
        and float(np.linalg.norm(points[0] - points[-1])) <= max(
            1.0,
            float(PAINT_PROJECTION_TUNING.smooth_max_linear_step_mm) * 2.0,
        )
    )

    if is_closed_path:
        points = _canonicalize_closed_source_path(
            points,
            pivot_xy=pivot_xy,
            start_reference_xy=tuple(tool_anchor) if tool_anchor is not None else None,
            translation_heading=translation_heading,
            side_reference_heading=paint_axis_heading,
            contact_segment_heading=contact_segment_heading,
            side_sign=config.side_sign,
        )

    command_rotation_sign = -1.0 if float(getattr(config, "rotation_direction_sign", 1.0)) < 0.0 else 1.0
    axis_vector = np.asarray(
        [
            float(np.cos(np.radians(contact_segment_heading))),
            float(np.sin(np.radians(contact_segment_heading))),
        ],
        dtype=float,
    )
    result: list[list[float]] = []
    snapshots: list[np.ndarray] = []
    diagnostics: list[dict[str, float | int]] = []
    previous_absolute_rotation: float | None = None
    cumulative_geometry_rotation = 0.0

    def _rotate_shape_about(current_points: np.ndarray, angle_deg: float, pivot_point: np.ndarray) -> np.ndarray:
        return np.array(
            [
                rotate_xy_about(
                    (float(point[0]), float(point[1])),
                    angle_deg,
                    (float(pivot_point[0]), float(pivot_point[1])),
                )
                for point in current_points
            ],
            dtype=float,
        )

    def _rotate_anchor_about(point: np.ndarray, angle_deg: float, pivot_point: np.ndarray) -> np.ndarray:
        return np.asarray(
            rotate_xy_about(
                (float(point[0]), float(point[1])),
                angle_deg,
                (float(pivot_point[0]), float(pivot_point[1])),
            ),
            dtype=float,
        )

    def _append_incremental_sample(
        *,
        reference_index: int,
        source_index: float,
        segment_heading: float,
        rotation_delta: float,
        segment_length: float,
        contact_index: int,
        contact_point: np.ndarray | None = None,
    ) -> None:
        """Emit the current mutable RTCP state."""
        nonlocal previous_absolute_rotation
        command_relative_rotation = cumulative_geometry_rotation * command_rotation_sign
        absolute_rotation = unwrap_degrees(
            base_rz if previous_absolute_rotation is None else previous_absolute_rotation,
            base_rz + command_relative_rotation,
        )
        command_rotation_delta = (
            0.0
            if previous_absolute_rotation is None
            else absolute_rotation - previous_absolute_rotation
        )
        contact_xy = points[contact_index] if contact_point is None else contact_point
        contact_error_mm = float(np.linalg.norm(contact_xy - np.asarray(pivot_xy, dtype=float)))

        result.append(
            _compose_pose(
                reference_pose=path[min(max(0, reference_index), len(path) - 1)],
                planar_i=planar_i,
                planar_j=planar_j,
                planar_a=float(tool_anchor[0]),
                planar_b=float(tool_anchor[1]),
                orthogonal_index=orthogonal_index,
                orthogonal_value=pivot_orthogonal,
                rotation_index=rotation_index,
                rotation_value=absolute_rotation,
                rx=rx,
                ry=ry,
                rz=rz,
            )
        )
        snapshots.append(points.copy())
        diagnostics.append(
            {
                "index": len(result) - 1,
                "source_index": float(source_index),
                "segment_length": segment_length,
                "segment_heading": segment_heading,
                "geometry_rotation": cumulative_geometry_rotation,
                "command_relative_rotation": command_relative_rotation,
                "rotation_delta_raw": rotation_delta,
                "rotation_delta_applied": command_rotation_delta,
                "current_rz": absolute_rotation,
                "contact_error_mm": contact_error_mm,
                "contact_correction_mm": 0.0,
            }
        )
        previous_absolute_rotation = absolute_rotation

    if len(points) == 1:
        translate_to_pivot = np.asarray(pivot_xy, dtype=float) - points[0]
        points = points + translate_to_pivot
        tool_anchor = tool_anchor + translate_to_pivot
        _append_incremental_sample(
            reference_index=0,
            source_index=0.0,
            segment_heading=float(contact_segment_heading),
            rotation_delta=0.0,
            segment_length=0.0,
            contact_index=0,
        )
        return result, snapshots, diagnostics

    initial_heading = _segment_heading_deg(points[0], points[1])
    initial_rotation = unwrap_degrees(0.0, contact_segment_heading - initial_heading)
    first_point = points[0].copy()
    points = _rotate_shape_about(points, initial_rotation, first_point)
    tool_anchor = _rotate_anchor_about(tool_anchor, initial_rotation, first_point)
    translate_to_pivot = np.asarray(pivot_xy, dtype=float) - points[0]
    points = points + translate_to_pivot
    tool_anchor = tool_anchor + translate_to_pivot
    cumulative_geometry_rotation = initial_rotation

    _append_incremental_sample(
        reference_index=0,
        source_index=0.0,
        segment_heading=initial_heading,
        rotation_delta=initial_rotation,
        segment_length=0.0,
        contact_index=0,
    )

    for segment_index in range(len(points) - 1):
        current_point = points[segment_index].copy()
        next_point = points[segment_index + 1].copy()
        segment_vector = next_point - current_point
        segment_length = float(np.linalg.norm(segment_vector))
        if segment_length <= 1e-9:
            continue
        segment_heading = _segment_heading_deg(current_point, next_point)
        rotation_delta = unwrap_degrees(0.0, contact_segment_heading - segment_heading)
        max_angular_step = max(0.1, float(PAINT_PROJECTION_TUNING.smooth_max_angular_step_deg))
        step_count = max(1, int(np.ceil(abs(rotation_delta) / max_angular_step)))
        start_points = points.copy()
        start_tool_anchor = tool_anchor.copy()
        start_geometry_rotation = cumulative_geometry_rotation
        pivot_array = np.asarray(pivot_xy, dtype=float)

        for step_index in range(1, step_count + 1):
            alpha = float(step_index) / float(step_count)
            step_rotation = rotation_delta * alpha
            step_points = start_points.copy()
            step_points[segment_index:] = _rotate_shape_about(
                start_points[segment_index:],
                step_rotation,
                current_point,
            )
            step_tool_anchor = _rotate_anchor_about(start_tool_anchor, step_rotation, current_point)
            contact_point = (
                (1.0 - alpha) * step_points[segment_index]
                + alpha * step_points[segment_index + 1]
            )
            contact_translation = pivot_array - contact_point
            step_points = step_points + contact_translation
            step_tool_anchor = step_tool_anchor + contact_translation

            points = step_points
            tool_anchor = step_tool_anchor
            cumulative_geometry_rotation = unwrap_degrees(
                start_geometry_rotation,
                start_geometry_rotation + step_rotation,
            )
            _append_incremental_sample(
                reference_index=segment_index + 1,
                source_index=float(segment_index) + alpha,
                segment_heading=segment_heading,
                rotation_delta=rotation_delta / float(step_count),
                segment_length=segment_length / float(step_count),
                contact_index=segment_index + 1,
                contact_point=pivot_array,
            )

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
    # _logger.debug(f"Refference pose: {reference_pose}")
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

    # _logger.debug(f"COMPOSE POSE: {pose}")
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
    start_reference_xy: tuple[float, float] | None = None,
    translation_heading: float,
    side_reference_heading: float,
    contact_segment_heading: float,
    side_sign: float,
) -> np.ndarray:
    """
    Give closed contours a pivot-aware start point and traversal direction.

    The first point should have a local segment already close to the requested
    contact heading. Distance to the pickup/source anchor is only a tie-breaker.
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
    reference_vec = (
        np.asarray([float(start_reference_xy[0]), float(start_reference_xy[1])], dtype=float)
        if start_reference_xy is not None
        else np.mean(contour, axis=0)
    )

    desired_heading = float(contact_segment_heading)
    desired_side_sign = 1.0 if float(side_sign) >= 0.0 else -1.0

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
                float(np.cos(np.radians(side_reference_heading))),
                float(np.sin(np.radians(side_reference_heading))),
            ],
            dtype=float,
        )
        normal = np.asarray([-axis_vector[1], axis_vector[0]], dtype=float)
        relative = aligned[1:] - pivot_vec if len(aligned) > 1 else aligned - pivot_vec
        if len(relative) == 0:
            return 0.0
        return float(np.mean(relative @ normal))

    def _initial_translation_run_length(candidate: np.ndarray) -> float:
        if len(candidate) < 2:
            return 0.0

        aligned_preview, _, _ = _preview_aligned(candidate)
        total = 0.0
        for index in range(len(aligned_preview) - 1):
            start = aligned_preview[index]
            end = aligned_preview[index + 1]
            segment_length = float(np.linalg.norm(end - start))
            if segment_length <= 1e-9:
                continue
            heading = _segment_heading_deg(start, end)
            heading_error = _angle_error_deg(heading, desired_heading)
            if heading_error > PAINT_PROJECTION_TUNING.rotation_deadband_deg:
                break
            total += segment_length
        return total

    best_ordered = contour
    best_key: tuple[float, float, float, float] | None = None
    for start_index in range(len(contour)):
        forward = np.roll(contour, -start_index, axis=0)
        reverse = forward[::-1].copy()
        reverse = np.roll(reverse, -np.argmin(np.linalg.norm(reverse - forward[0], axis=1)), axis=0)
        for candidate in (forward, reverse):
            aligned_preview, heading, _ = _preview_aligned(candidate)
            heading_error = _angle_error_deg(heading, desired_heading)
            heading_penalty = max(
                0.0,
                heading_error - float(PAINT_PROJECTION_TUNING.rotation_deadband_deg),
            )
            side_score = _side_score(aligned_preview)
            side_penalty = 0.0 if side_score * desired_side_sign >= 0.0 else 1.0
            initial_run_length = _initial_translation_run_length(candidate)
            anchor_distance = float(np.linalg.norm(candidate[0] - reference_vec))
            key = (side_penalty, heading_penalty, -initial_run_length, anchor_distance)
            if best_key is None or key < best_key:
                best_key = key
                best_ordered = candidate

    return np.vstack([best_ordered, best_ordered[:1]])

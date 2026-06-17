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


def project_paint_motion_geometry(
    path: list[list[float]],
    pivot_pose: list[float],
    config: PaintSimulationConfig,
    anchor_xy: tuple[float, float] | None = None,
    source_rotation_deg: float = 0.0,
) -> tuple[list[list[float]], list[np.ndarray], list[dict[str, float | int]]]:
    """Project a source paint path into pickup/pivot motion geometry around the configured base pose."""
    if not path:
        return [], [], []
    planar_i, planar_j = config.planar_coordinate_indices
    source_planar_i, source_planar_j = config.source_planar_coordinate_indices
    orthogonal_index = config.orthogonal_position_index
    rotation_index = config.rotation_index
    source_anchor = (
        np.asarray([float(anchor_xy[0]), float(anchor_xy[1])], dtype=float)
        if anchor_xy is not None else None
    )
    if len(path) == 1:
        point = path[0]
        planar_point = np.array([[float(point[source_planar_i]), float(point[source_planar_j])]], dtype=float)
        if source_anchor is None:
            return [list(point)], [planar_point], []
        projected_pose = list(point)
        while len(projected_pose) < 6:
            projected_pose.append(0.0)
        projected_pose[planar_i] = float(source_anchor[0])
        projected_pose[planar_j] = float(source_anchor[1])
        return [projected_pose], [planar_point], []

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

    _logger.debug(f"orientation_overrides {orientation_overrides}")

    base_rz = (
        float(pivot_pose[rotation_index])
        if len(pivot_pose) > rotation_index else float(path[0][rotation_index])
    )
    _logger.debug(f"base_rz {base_rz}")

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

    tcp_anchor = source_anchor.copy() if source_anchor is not None else None
    _logger.debug(f"tcp_anchor {tcp_anchor}")

    source_rotation = float(source_rotation_deg or 0.0)
    if len(points) < 2:
        anchor_point = tcp_anchor if tcp_anchor is not None else points[0]
        return (
            [
                _compose_pose(
                    reference_pose=path[0],
                    planar_i=planar_i,
                    planar_j=planar_j,
                    planar_a=float(anchor_point[0]),
                    planar_b=float(anchor_point[1]),
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

    def _rotate_point(point: np.ndarray, angle_deg: float, pivot_xy: tuple[float, float]) -> np.ndarray:
        return np.asarray(
            rotate_xy_about((float(point[0]), float(point[1])), angle_deg, pivot_xy),
            dtype=float,
        )

    if abs(source_rotation) > 1e-9:
        rotation_anchor = (
            tcp_anchor
            if tcp_anchor is not None
            else np.asarray([float(np.mean(points[:, 0])), float(np.mean(points[:, 1]))], dtype=float)
        )
        points = _rotate_shape(
            points,
            source_rotation,
            (float(rotation_anchor[0]), float(rotation_anchor[1])),
        )

    def _segment_heading_deg(point_a: np.ndarray, point_b: np.ndarray) -> float:
        dx = float(point_b[0] - point_a[0])
        dy = float(point_b[1] - point_a[1])
        return float(np.degrees(np.arctan2(dy, dx)))

    def _arc_rotation_schedule(source_points: np.ndarray) -> list[float]:
        """Build per-segment rotation deltas for chorded arcs, not isolated corners."""
        segment_count = len(source_points) - 1
        if segment_count < 3:
            return [0.0 for _ in range(max(0, segment_count))]

        segment_lengths: list[float] = []
        segment_starts: list[float] = []
        segment_headings: list[float] = []
        total_distance = 0.0
        for segment_index in range(segment_count):
            start = source_points[segment_index]
            end = source_points[segment_index + 1]
            segment_starts.append(total_distance)
            segment_length = float(np.linalg.norm(end - start))
            segment_lengths.append(segment_length)
            heading = _segment_heading_deg(start, end)
            if segment_headings:
                heading = unwrap_degrees(segment_headings[-1], heading)
            segment_headings.append(heading)
            total_distance += segment_length

        turn_candidates: list[tuple[int, float, float]] = []
        for segment_index in range(1, segment_count):
            turn = segment_headings[segment_index] - segment_headings[segment_index - 1]
            abs_turn = abs(turn)
            if abs_turn < float(PAINT_PROJECTION_TUNING.rotation_deadband_deg):
                continue
            if abs_turn >= float(PAINT_PROJECTION_TUNING.sharp_corner_rotation_threshold_deg):
                continue
            turn_candidates.append((segment_index, turn, segment_starts[segment_index]))

        if len(turn_candidates) < 2:
            return [0.0 for _ in range(segment_count)]

        lookahead_distance = max(
            float(PAINT_PROJECTION_TUNING.smooth_max_linear_step_mm) * 15.0,
            float(PAINT_PROJECTION_TUNING.smooth_max_linear_step_mm),
        )
        neighbor_distance = lookahead_distance * 2.0
        scheduled_deltas = [0.0 for _ in range(segment_count)]

        for candidate_index, turn, turn_distance in turn_candidates:
            has_arc_neighbor = any(
                other_index != candidate_index
                and (other_turn > 0.0) == (turn > 0.0)
                and abs(other_distance - turn_distance) <= neighbor_distance
                for other_index, other_turn, other_distance in turn_candidates
            )
            if not has_arc_neighbor:
                continue

            start_distance = max(0.0, turn_distance - lookahead_distance)
            end_distance = turn_distance
            span = end_distance - start_distance
            if span <= 1e-9:
                continue
            for segment_index, segment_length in enumerate(segment_lengths):
                if segment_length <= 1e-9:
                    continue
                segment_start = segment_starts[segment_index]
                segment_end = segment_start + segment_length
                overlap = max(0.0, min(segment_end, end_distance) - max(segment_start, start_distance))
                if overlap <= 1e-9:
                    continue
                scheduled_deltas[segment_index] += -turn * (overlap / span)

        return scheduled_deltas

    pivot_xy = (pivot_x, pivot_y)
    points = _canonicalize_closed_source_path(
        points,
        pivot_xy=pivot_xy,
        start_reference_xy=tuple(tcp_anchor) if tcp_anchor is not None else None,
        translation_heading=translation_heading,
        side_reference_heading=paint_axis_heading,
        contact_segment_heading=contact_segment_heading,
        side_sign=config.side_sign,
    )

    # First, orient the source shape so its first segment points along the
    # configured paint axis. This defines the starting pickup orientation.
    initial_heading = _segment_heading_deg(points[0], points[1])
    initial_rotation = unwrap_degrees(0.0, contact_segment_heading - initial_heading)
    first_point = (float(points[0][0]), float(points[0][1]))
    points = _rotate_shape(points, initial_rotation, (float(points[0][0]), float(points[0][1])))
    if tcp_anchor is not None:
        tcp_anchor = _rotate_point(tcp_anchor, initial_rotation, first_point)

    # Then translate the rotated shape so its first point sits exactly on the
    # physical pivot/base position used by the robot.
    translate_to_pivot = np.array([pivot_x - float(points[0][0]), pivot_y - float(points[0][1])], dtype=float)
    points = points + translate_to_pivot
    if tcp_anchor is None:
        tcp_anchor = np.asarray(_centroid_xy(points), dtype=float)
    else:
        tcp_anchor = tcp_anchor + translate_to_pivot

    current_rz = unwrap_degrees(base_rz, base_rz + initial_rotation)
    arc_rotation_deltas = _arc_rotation_schedule(points)
    result: list[list[float]] = []
    snapshots: list[np.ndarray] = []
    diagnostics: list[dict[str, float | int]] = []
    result.append(
        _compose_pose(
            reference_pose=path[0],
            planar_i=planar_i,
            planar_j=planar_j,
            planar_a=float(tcp_anchor[0]),
            planar_b=float(tcp_anchor[1]),
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
            result.append(
                _compose_pose(
                    reference_pose=path[min(index + 1, len(path) - 1)],
                    planar_i=planar_i,
                    planar_j=planar_j,
                    planar_a=float(tcp_anchor[0]),
                    planar_b=float(tcp_anchor[1]),
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
        scheduled_arc_delta = (
            float(arc_rotation_deltas[index])
            if index < len(arc_rotation_deltas) else 0.0
        )
        using_scheduled_arc_delta = (
            abs(scheduled_arc_delta) > 1e-9
            and abs(rotation_delta_raw) < float(PAINT_PROJECTION_TUNING.sharp_corner_rotation_threshold_deg)
        )
        rotation_delta = (
            scheduled_arc_delta
            if using_scheduled_arc_delta
            else rotation_delta_raw
        )

        # Ignore tiny heading noise to avoid jittering the projected RZ.
        if (
            not using_scheduled_arc_delta
            and abs(rotation_delta) < PAINT_PROJECTION_TUNING.rotation_deadband_deg
        ):
            rotation_delta = 0.0
        emit_corner_rotation = (
            abs(rotation_delta) >= float(PAINT_PROJECTION_TUNING.sharp_corner_rotation_threshold_deg)
        )
        if abs(rotation_delta) > 1e-9 and emit_corner_rotation:
            # Rotate the whole shape around the fixed pivot in small emitted
            # steps. A sharp corner is a rotation about the current contact
            # point; sending only the final pose lets the controller interpolate
            # linearly and can lift the real edge off the pivot.
            max_angular_step = max(0.1, float(PAINT_PROJECTION_TUNING.smooth_max_angular_step_deg))
            rotation_steps = max(1, int(np.ceil(abs(rotation_delta) / max_angular_step)))
            step_delta = rotation_delta / float(rotation_steps)
            for _ in range(rotation_steps):
                points = _rotate_shape(points, step_delta, pivot_xy)
                tcp_anchor = _rotate_point(tcp_anchor, step_delta, pivot_xy)
                current_rz = unwrap_degrees(current_rz, current_rz + step_delta)
                contact_error_mm = float(
                    np.linalg.norm(points[index] - np.asarray(pivot_xy, dtype=float))
                )
                result.append(
                    _compose_pose(
                        reference_pose=path[min(index, len(path) - 1)],
                        planar_i=planar_i,
                        planar_j=planar_j,
                        planar_a=float(tcp_anchor[0]),
                        planar_b=float(tcp_anchor[1]),
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
                        "segment_heading": segment_heading,
                        "rotation_delta_raw": step_delta,
                        "rotation_delta_applied": step_delta,
                        "current_rz": current_rz,
                        "contact_error_mm": contact_error_mm,
                        "contact_correction_mm": 0.0,
                    }
                )

        elif abs(rotation_delta) > 1e-9:
            # For arcs, emit combined rotation+contact-advance samples. This
            # keeps the active edge point on the pivot while avoiding the
            # rotate-then-translate stepping that is visible on rounded corners.
            max_angular_step = max(0.1, float(PAINT_PROJECTION_TUNING.smooth_max_angular_step_deg))
            max_linear_step = max(0.1, float(PAINT_PROJECTION_TUNING.smooth_max_linear_step_mm))
            blend_steps = max(
                1,
                int(np.ceil(abs(rotation_delta) / max_angular_step)),
                int(np.ceil(segment_length / max_linear_step)),
            )
            start_points = points.copy()
            start_tcp_anchor = tcp_anchor.copy()
            start_rz = current_rz
            for step_index in range(1, blend_steps + 1):
                alpha = float(step_index) / float(blend_steps)
                step_rotation = rotation_delta * alpha
                step_points = _rotate_shape(start_points, step_rotation, pivot_xy)
                step_tcp_anchor = _rotate_point(start_tcp_anchor, step_rotation, pivot_xy)
                contact_point = (1.0 - alpha) * step_points[index] + alpha * step_points[index + 1]
                contact_translation = np.asarray(pivot_xy, dtype=float) - contact_point
                step_points = step_points + contact_translation
                step_tcp_anchor = step_tcp_anchor + contact_translation
                step_rz = unwrap_degrees(start_rz, start_rz + step_rotation)
                contact_error_mm = float(np.linalg.norm(contact_point + contact_translation - np.asarray(pivot_xy, dtype=float)))
                result.append(
                    _compose_pose(
                        reference_pose=path[min(index + 1, len(path) - 1)],
                        planar_i=planar_i,
                        planar_j=planar_j,
                        planar_a=float(step_tcp_anchor[0]),
                        planar_b=float(step_tcp_anchor[1]),
                        orthogonal_index=orthogonal_index,
                        orthogonal_value=pivot_orthogonal,
                        rotation_index=rotation_index,
                        rotation_value=step_rz,
                        rx=rx,
                        ry=ry,
                        rz=rz,
                    )
                )
                snapshots.append(step_points.copy())
                diagnostics.append(
                    {
                        "index": index + 1,
                        "segment_length": segment_length / float(blend_steps),
                        "segment_heading": segment_heading,
                        "rotation_delta_raw": rotation_delta / float(blend_steps),
                        "rotation_delta_applied": rotation_delta / float(blend_steps),
                        "current_rz": step_rz,
                        "contact_error_mm": contact_error_mm,
                        "contact_correction_mm": 0.0,
                    }
                )
            points = step_points
            tcp_anchor = step_tcp_anchor
            current_rz = step_rz
            continue

        # After any rotation, move the next source edge point exactly onto the
        # physical pivot. When the segment has been aligned with the configured
        # contact heading this is equivalent to axis travel, but it also avoids
        # contact drift from small heading errors, deadband, and noisy arcs.
        contact_translation = np.asarray(pivot_xy, dtype=float) - points[index + 1]
        axis_projection = axis_vector * segment_length * config.direction_sign
        contact_correction = contact_translation - axis_projection
        points = points + contact_translation
        tcp_anchor = tcp_anchor + contact_translation
        contact_error_mm = float(np.linalg.norm(points[index + 1] - np.asarray(pivot_xy, dtype=float)))
        result.append(
            _compose_pose(
                reference_pose=path[min(index + 1, len(path) - 1)],
                planar_i=planar_i,
                planar_j=planar_j,
                planar_a=float(tcp_anchor[0]),
                planar_b=float(tcp_anchor[1]),
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
                "contact_error_mm": contact_error_mm,
                "contact_correction_mm": float(np.linalg.norm(contact_correction)),
            }
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

"""Paint contact-motion projection helpers.

This module converts a prepared workpiece contour into robot poses that keep a
chosen contour point touching the fixed paint contact axis. The calculation is
done in the active 2D motion plane from ``PaintSimulationConfig``. The shape is
rotated and translated so each sampled point contacts the paint axis in turn;
it is not orbiting around the axis.

* ``xy_z_rz`` uses X/Y as the contact plane and RZ as the active rotation.
* ``xz_y_ry`` uses X/Z as the contact plane and RY as the active rotation.

Performance notes:
* Point rotations are vectorized with NumPy instead of per-point Python loops.
* Projection snapshots are disabled by default to avoid O(n^2) memory copying
  on dense contours. If you need old debug snapshots, set either
  ``config.save_projection_snapshots = True`` or
  ``PAINT_PROJECTION_TUNING.save_projection_snapshots = True``.
"""

import logging

import numpy as np

from src.engine.geometry.planar import normalize_degrees, unwrap_degrees
from src.robot_systems.paint.processes.paint.config import (
    PAINT_PROJECTION_TUNING,
    PaintSimulationConfig,
)

_logger = logging.getLogger("Core")
_EMPTY_SNAPSHOT = np.empty((0, 2), dtype=float)
_CONTACT_HEADING_OPPOSES_TRANSLATION_DEG = 180.0


def rebase_contact_motion_path_to_zero_start_rotation(
        path: list[list[float]],
        config: PaintSimulationConfig,
) -> list[list[float]]:
    """Shift a paint contact-motion path so its active rotation starts at zero."""
    if not path:
        return []

    rotation_index = config.rotation_index
    rebased = [list(pose) for pose in path]
    start_rz = float(rebased[0][rotation_index]) if len(rebased[0]) > rotation_index else 0.0

    for pose in rebased:
        if len(pose) > rotation_index:
            pose[rotation_index] = unwrap_degrees(0.0, float(pose[rotation_index]) - start_rz)
    return rebased


def _rotate_points_about(points, angle_deg: float, pivot) -> np.ndarray:
    """Vectorized 2D rotation around ``pivot``.

    Accepts either an ``(N, 2)`` array or one ``(2,)`` point. Returns the same
    dimensionality as the input.
    """
    arr = np.asarray(points, dtype=float)
    single = arr.ndim == 1
    if single:
        arr2 = arr.reshape(1, 2)
    else:
        arr2 = arr

    if arr2.size == 0:
        return arr.copy()

    pivot_vec = np.asarray(pivot, dtype=float).reshape(2)
    theta = np.radians(float(angle_deg))
    c = float(np.cos(theta))
    s = float(np.sin(theta))

    shifted = arr2 - pivot_vec
    out = np.empty_like(shifted)
    out[:, 0] = shifted[:, 0] * c - shifted[:, 1] * s
    out[:, 1] = shifted[:, 0] * s + shifted[:, 1] * c
    out += pivot_vec
    return out[0] if single else out


def _save_projection_snapshots(config: PaintSimulationConfig) -> bool:
    """Return whether expensive full-shape debug snapshots should be stored."""
    return bool(
        getattr(
            config,
            "save_projection_snapshots",
            getattr(PAINT_PROJECTION_TUNING, "save_projection_snapshots", False),
        )
    )


def project_paint_contact_motion_continuous(
        path: list[list[float]],
        paint_axis_pose: list[float],
        config: PaintSimulationConfig,
        anchor_xy: tuple[float, float] | None = None,
        source_rotation_deg: float = 0.0,
) -> tuple[list[list[float]], list[np.ndarray], list[dict[str, float | int]]]:
    """Project a dense contour into paint-axis contact motion.

    The input path is expected to be the prepared paint source contour. The
    algorithm mirrors the legacy KAREL RTCP loop: the current contour point is
    the paint-axis contact, the remaining workpiece is rotated around that
    point, then translated along the contact axis so the next contour point
    becomes the new contact. The geometry rotation is kept separate from the
    robot command rotation sign.
    """
    if not path:
        return [], [], []

    # Resolve which 2D plane this job uses.
    #
    # The legacy KAREL program operated in X/Y and stored the accumulated
    # rotation in the position register orientation field. This implementation
    # supports both paint planes:
    #   * xy_z_rz: source X/Y -> robot X/Y, active rotation RZ
    #   * xz_y_ry: source X/Y -> robot X/Z, active rotation RY
    # The following indices let the same RTCP math run in either plane.
    planar_i, planar_j = config.planar_coordinate_indices
    source_planar_i, source_planar_j = config.source_planar_coordinate_indices
    orthogonal_index = config.orthogonal_position_index
    rotation_index = config.rotation_index

    # The fixed RTCP/pivot location in robot coordinates. During projection, the
    # active source point is repeatedly brought back to this exact 2D point.
    pivot_pose = paint_axis_pose
    pivot_xy = np.asarray(
        [float(paint_axis_pose[planar_i]), float(paint_axis_pose[planar_j])],
        dtype=float,
    )
    pivot_xy_tuple = (float(pivot_xy[0]), float(pivot_xy[1]))
    pivot_orthogonal = (
        float(paint_axis_pose[orthogonal_index])
        if len(paint_axis_pose) > orthogonal_index
        else float(path[0][orthogonal_index])
    )

    # The non-active orientation components are fixed from the pivot pose unless
    # the motion-plane config overrides them. Only rotation_index changes during
    # the simulated rolling/painting transform.
    rx = float(paint_axis_pose[3]) if len(paint_axis_pose) >= 4 else float(path[0][3])
    ry = float(paint_axis_pose[4]) if len(paint_axis_pose) >= 5 else float(path[0][4])
    rz = float(paint_axis_pose[5]) if len(paint_axis_pose) >= 6 else float(path[0][5])
    orientation_overrides = config.orientation_overrides_deg
    rx = float(orientation_overrides.get("rx", rx))
    ry = float(orientation_overrides.get("ry", ry))
    rz = float(orientation_overrides.get("rz", rz))
    base_rz = (
        float(paint_axis_pose[rotation_index])
        if len(paint_axis_pose) > rotation_index
        else float(path[0][rotation_index])
    )

    # Copy only the source contact plane from the incoming path. This mutable
    # array is the Python equivalent of the KAREL arprPosTemp[] array: each loop
    # iteration modifies the remaining workpiece points in-place conceptually.
    points = np.asarray(
        [[float(point[source_planar_i]), float(point[source_planar_j])] for point in path],
        dtype=float,
    )
    if points.size == 0:
        return [], [], []

    # Tool/workpiece anchor to command. In the legacy code this is analogous to
    # the workpiece center/static offset registers: it is not necessarily the
    # current contact point, but it moves as the contour is rotated/translated.
    tool_anchor = (
        np.asarray([float(anchor_xy[0]), float(anchor_xy[1])], dtype=float)
        if anchor_xy is not None
        else np.mean(points, axis=0)
    )

    # Apply any pre-rotation carried from pickup alignment before the RTCP loop
    # starts. This is the equivalent of rotating the input point array around the
    # selected workpiece anchor before calculating the rolling motion.
    source_rotation = float(source_rotation_deg or 0.0)
    if abs(source_rotation) > 1e-9:
        points = _rotate_points_about(points, source_rotation, tool_anchor)

    # Determine the physical direction the contact segment should have at the
    # pivot. translation_heading is the direction of travel along the paint axis;
    # contact_segment_heading is the tangent heading the local contour segment
    # should match while it passes through the RTCP/pivot.
    paint_axis_heading = normalize_degrees(base_rz + config.paint_axis_offset_deg)
    translation_heading = float(paint_axis_heading)
    if config.direction_sign < 0:
        translation_heading = normalize_degrees(translation_heading + 180.0)
    contact_segment_heading = normalize_degrees(
        translation_heading + _CONTACT_HEADING_OPPOSES_TRANSLATION_DEG
    )

    is_closed_path = (
            len(points) >= 3
            and float(np.linalg.norm(points[0] - points[-1]))
            <= max(1.0, float(PAINT_PROJECTION_TUNING.smooth_max_linear_step_mm) * 2.0)
    )

    if is_closed_path:
        # Closed contours have no natural start. Choose the start/order that is
        # closest to the pickup anchor and already compatible with the desired
        # contact side and tangent. This replaces the old fixed PR ordering with
        # a deterministic pivot-aware ordering.
        points = _canonicalize_closed_source_path(
            points,
            pivot_xy=pivot_xy_tuple,
            start_reference_xy=tuple(tool_anchor),
            translation_heading=translation_heading,
            side_reference_heading=paint_axis_heading,
            contact_segment_heading=contact_segment_heading,
            side_sign=config.side_sign,
        )

    command_rotation_sign = -1.0 if float(getattr(config, "rotation_direction_sign", 1.0)) < 0.0 else 1.0
    save_snapshots = _save_projection_snapshots(config)

    result: list[list[float]] = []
    snapshots: list[np.ndarray] = []
    diagnostics: list[dict[str, float | int]] = []
    previous_absolute_rotation: float | None = None
    cumulative_geometry_rotation = 0.0

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
        """Emit one robot command sample from the current mutable RTCP state."""
        nonlocal previous_absolute_rotation

        # Convert geometry rotation to robot command rotation. Some motion-plane
        # definitions need the robot axis to move opposite the mathematical
        # workpiece rotation, so the sign is applied only at command emission.
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
        contact_error_mm = float(np.linalg.norm(contact_xy - pivot_xy))

        # The commanded TCP/tool point is the transformed anchor, not the contact
        # point itself. The contact point is constrained to the pivot; the anchor
        # describes where the robot TCP should be for that workpiece state.
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
        snapshots.append(points.copy() if save_snapshots else _EMPTY_SNAPSHOT)
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
        # Degenerate one-point contour: no tangent can be computed, so only
        # translate the point/anchor onto the pivot and emit one stationary pose.
        translate_to_pivot = pivot_xy - points[0]
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

    # Initial alignment:
    # Rotate the whole workpiece around the first contour point so the first
    # segment has the required contact tangent, then translate the first point
    # onto the fixed RTCP/pivot. This corresponds to the KAREL setup before the
    # FOR loop starts updating the remaining arprPosTemp[] points.
    initial_heading = _segment_heading_deg(points[0], points[1])
    initial_rotation = unwrap_degrees(0.0, contact_segment_heading - initial_heading)
    first_point = points[0].copy()
    points = _rotate_points_about(points, initial_rotation, first_point)
    tool_anchor = _rotate_points_about(tool_anchor, initial_rotation, first_point)

    translate_to_pivot = pivot_xy - points[0]
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

    pivot_array = pivot_xy
    # Config values used by the projection loop. The deadband is also used by
    # closed-path canonicalization; max_angular_step limits how much active-axis
    # rotation any emitted sample can represent.
    rotation_deadband_deg = float(
        getattr(PAINT_PROJECTION_TUNING, "rotation_deadband_deg", 0.5)
    )
    max_angular_step = max(
        0.1,
        float(PAINT_PROJECTION_TUNING.smooth_max_angular_step_deg),
    )

    for segment_index in range(len(points) - 1):
        # Current/next are already in the mutable projected state, not the
        # original source coordinates. Each iteration consumes the current
        # contact point and prepares the next one.
        current_point = points[segment_index].copy()
        next_point = points[segment_index + 1].copy()
        segment_vector = next_point - current_point
        segment_length = float(np.linalg.norm(segment_vector))
        if segment_length <= 1e-9:
            continue

        # Equivalent to the KAREL angle calculation between pr_pos and
        # prPosNext. The desired tangent is fixed; the delta is the incremental
        # rotation needed to make this local segment match that tangent.
        segment_heading = _segment_heading_deg(current_point, next_point)
        rotation_delta = unwrap_degrees(0.0, contact_segment_heading - segment_heading)

        # Split larger corrections into several emitted samples. This mirrors
        # the legacy half/intermediate circular-motion idea, but uses uniform
        # substeps so the downstream trajectory has bounded rotation increments.
        step_count = max(1, int(np.ceil(abs(rotation_delta) / max_angular_step)))
        start_points = points.copy()
        start_tool_anchor = tool_anchor.copy()
        start_geometry_rotation = cumulative_geometry_rotation

        for step_index in range(1, step_count + 1):
            alpha = float(step_index) / float(step_count)
            step_rotation = rotation_delta * alpha

            # Rotate the unconsumed part of the workpiece around the current
            # contact point. Points before segment_index have already passed the
            # pivot and are left unchanged, matching the KAREL loop that updates
            # j=i..l for the remaining points.
            step_points = start_points.copy()
            step_points[segment_index:] = _rotate_points_about(
                start_points[segment_index:],
                step_rotation,
                current_point,
            )
            # The commanded anchor must undergo the same rigid transform as the
            # workpiece so the TCP follows the transformed part geometry.
            step_tool_anchor = _rotate_points_about(
                start_tool_anchor,
                step_rotation,
                current_point,
            )

            # Move along the current segment while the rotation substep is being
            # applied. alpha selects the intermediate contact between current
            # and next; then a translation brings that contact exactly onto the
            # fixed pivot. This is the RTCP constraint: contact_error should be 0.
            contact_point = (
                    (1.0 - alpha) * step_points[segment_index]
                    + alpha * step_points[segment_index + 1]
            )
            contact_translation = pivot_array - contact_point
            step_points = step_points + contact_translation
            step_tool_anchor = step_tool_anchor + contact_translation

            # Commit this intermediate RTCP state. The next substep or next
            # source segment starts from this transformed workpiece state.
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
    """Return the heading of the segment from ``point_a`` to ``point_b``.

        The heading is measured in the XY plane relative to the positive X-axis,
        with positive angles rotating counter-clockwise. The result is in the
        range [-180°, 180°].

        Examples:
            (0, 0) → (1, 0)  ->   0°
            (0, 0) → (0, 1)  ->  90°
            (0, 0) → (-1, 0) -> 180°
            (0, 0) → (0, -1) -> -90°
        """
    dx = float(point_b[0] - point_a[0])
    dy = float(point_b[1] - point_a[1])
    return float(np.degrees(np.arctan2(dy, dx)))


def _angle_error_deg(a: float, b: float) -> float:
    """Return the smallest angular error between two angles in degrees.

     The comparison accounts for axis-equivalent rotations (e.g. 0° ≡ 360°,
     -180° ≡ 180°) by first unwrapping ``b`` into the revolution closest to
     ``a`` before computing the absolute difference.

     Examples:
         _angle_error_deg(10, 370)    -> 0.0
         _angle_error_deg(179, -181)  -> 0.0
         _angle_error_deg(10, 20)     -> 10.0
     """
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
    """Give closed contours a pivot-aware start point and traversal direction."""
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
    rotation_deadband = float(PAINT_PROJECTION_TUNING.rotation_deadband_deg)

    axis_vector = np.asarray(
        [
            float(np.cos(np.radians(side_reference_heading))),
            float(np.sin(np.radians(side_reference_heading))),
        ],
        dtype=float,
    )
    normal = np.asarray([-axis_vector[1], axis_vector[0]], dtype=float)

    def _preview_aligned(candidate: np.ndarray) -> tuple[np.ndarray, float, float]:
        heading = _segment_heading_deg(candidate[0], candidate[1])
        rotation = unwrap_degrees(0.0, desired_heading - heading)
        rotated = _rotate_points_about(candidate, rotation, candidate[0])
        translated = rotated + (pivot_vec - rotated[0])
        return translated, heading, rotation

    def _side_score(aligned: np.ndarray) -> float:
        relative = aligned[1:] - pivot_vec if len(aligned) > 1 else aligned - pivot_vec
        if len(relative) == 0:
            return 0.0
        return float(np.mean(relative @ normal))

    def _initial_translation_run_length(candidate: np.ndarray) -> float:
        if len(candidate) < 2:
            return 0.0

        aligned_preview, _, _ = _preview_aligned(candidate)
        deltas = np.diff(aligned_preview, axis=0)
        lengths = np.linalg.norm(deltas, axis=1)
        headings = np.degrees(np.arctan2(deltas[:, 1], deltas[:, 0]))

        total = 0.0
        for segment_length, heading in zip(lengths, headings):
            segment_length = float(segment_length)
            if segment_length <= 1e-9:
                continue
            if _angle_error_deg(float(heading), desired_heading) > rotation_deadband:
                break
            total += segment_length
        return total

    best_ordered = contour
    best_key: tuple[float, float, float, float] | None = None

    for start_index in range(len(contour)):
        forward = np.roll(contour, -start_index, axis=0)
        reverse = forward[::-1].copy()
        reverse = np.roll(
            reverse,
            -int(np.argmin(np.linalg.norm(reverse - forward[0], axis=1))),
            axis=0,
        )

        for candidate in (forward, reverse):
            aligned_preview, heading, _ = _preview_aligned(candidate)
            heading_error = _angle_error_deg(heading, desired_heading)
            heading_penalty = max(0.0, heading_error - rotation_deadband)
            side_score = _side_score(aligned_preview)
            side_penalty = 0.0 if side_score * desired_side_sign >= 0.0 else 1.0
            initial_run_length = _initial_translation_run_length(candidate)
            anchor_distance = float(np.linalg.norm(candidate[0] - reference_vec))
            key = (side_penalty, heading_penalty, -initial_run_length, anchor_distance)

            if best_key is None or key < best_key:
                best_key = key
                best_ordered = candidate

    return np.vstack([best_ordered, best_ordered[:1]])


# Compatibility aliases for old pivot/projection naming.
project_paint_motion_geometry_continuous = project_paint_contact_motion_continuous
rebase_projected_paint_path_to_zero_start_rz = rebase_contact_motion_path_to_zero_start_rotation

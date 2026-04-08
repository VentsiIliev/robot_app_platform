from src.engine.robot.path_interpolation.spline_interpolation import interpolate_path_spline_with_lambda
import numpy as np


def _cumulative_arc_length_mm(path: list[list[float]]) -> np.ndarray:
    path_array = np.array(path, dtype=float)
    if len(path_array) == 0:
        return np.array([], dtype=float)
    if len(path_array) == 1:
        return np.array([0.0], dtype=float)
    diffs = np.diff(path_array[:, :3], axis=0)
    seg_lengths = np.linalg.norm(diffs, axis=1)
    return np.concatenate([[0.0], np.cumsum(seg_lengths)])


def _local_cubic_fit_value(samples_s: np.ndarray, samples_v: np.ndarray, eval_s: float) -> float:
    if len(samples_s) == 0:
        return float(eval_s)
    degree = min(3, len(samples_s) - 1)
    if degree <= 0:
        return float(samples_v[0])
    centered_s = samples_s - float(eval_s)
    try:
        coeffs = np.polyfit(centered_s, samples_v, degree)
        return float(np.polyval(coeffs, 0.0))
    except Exception:
        weights = np.ones(len(samples_v), dtype=float)
        return float(np.average(samples_v, weights=weights))


def pre_smooth_path_for_interpolation(
    path: list[list[float]],
    window_size: int = 5,
    passes: int = 1,
    preserve_corner_angle_deg: float = 35.0,
    max_deviation_mm: float = 1.0,
) -> list[list[float]]:
    """Locally smooth noisy robot-space paths with cubic fitting and deviation clamping.

    The fitter works over arc length in robot space, preserves endpoints and
    protected corners, and clamps each adjusted sample to a hard geometric
    deviation bound in mm so the smoothed path cannot drift off the source
    geometry.
    """
    if len(path) < 3:
        return [list(point) for point in path]

    window_size = max(3, int(window_size))
    if window_size % 2 == 0:
        window_size += 1
    radius = window_size // 2

    current = np.array(path, dtype=float)
    xyz = current[:, :3].copy()
    original_xyz = xyz.copy()
    arc_s = _cumulative_arc_length_mm(path)
    turn_angles = _compute_turn_angles_deg(path)
    preserve_mask = turn_angles >= float(preserve_corner_angle_deg)
    preserve_mask[0] = True
    preserve_mask[-1] = True
    max_deviation_mm = max(0.0, float(max_deviation_mm))

    for _ in range(max(1, int(passes))):
        next_xyz = xyz.copy()
        for i in range(1, len(xyz) - 1):
            if preserve_mask[i]:
                continue
            start = max(0, i - radius)
            end = min(len(xyz), i + radius + 1)
            local_preserve = preserve_mask[start:end]
            valid_mask = ~local_preserve
            valid_mask[i - start] = True
            local_s = arc_s[start:end][valid_mask]
            local_xyz = xyz[start:end][valid_mask]
            if len(local_s) < 3:
                continue
            eval_s = float(arc_s[i])
            fitted = np.array(
                [
                    _local_cubic_fit_value(local_s, local_xyz[:, axis], eval_s)
                    for axis in range(3)
                ],
                dtype=float,
            )
            delta = fitted - original_xyz[i]
            delta_norm = float(np.linalg.norm(delta))
            if delta_norm > max_deviation_mm > 1e-9:
                fitted = original_xyz[i] + (delta / delta_norm) * max_deviation_mm
            next_xyz[i] = fitted
        next_xyz[0] = xyz[0]
        next_xyz[-1] = xyz[-1]
        xyz = next_xyz

    result = current.copy()
    result[:, :3] = xyz
    return result.tolist()


def _compute_normalized_arc_length(path: list[list[float]]) -> tuple[np.ndarray, float]:
    path_array = np.array(path, dtype=float)
    if len(path_array) < 2:
        return np.array([0.0]), 0.0
    diffs = np.diff(path_array[:, :3], axis=0)
    seg_lengths = np.linalg.norm(diffs, axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(seg_lengths)])
    total_length = float(cumulative[-1])
    if total_length <= 1e-9:
        return np.linspace(0.0, 1.0, len(path_array)), total_length
    return cumulative / total_length, total_length


def _compute_turn_angles_deg(path: list[list[float]]) -> np.ndarray:
    path_array = np.array(path, dtype=float)
    n = len(path_array)
    angles = np.zeros(n, dtype=float)
    if n < 3:
        return angles
    diffs = np.diff(path_array[:, :3], axis=0)
    norms = np.linalg.norm(diffs, axis=1)
    for i in range(1, n - 1):
        n0 = norms[i - 1]
        n1 = norms[i]
        if n0 <= 1e-9 or n1 <= 1e-9:
            continue
        v0 = diffs[i - 1] / n0
        v1 = diffs[i] / n1
        dot = float(np.clip(np.dot(v0, v1), -1.0, 1.0))
        angles[i] = float(np.degrees(np.arccos(dot)))
    return angles


def _build_corner_intervals(
    path: list[list[float]],
    target_spacing_mm: float,
    corner_angle_threshold_deg: float,
    corner_window_spacing_multiplier: float,
) -> list[tuple[float, float]]:
    t_norm, total_length = _compute_normalized_arc_length(path)
    if total_length <= 1e-9:
        return []
    turn_angles = _compute_turn_angles_deg(path)
    half_window = (target_spacing_mm * corner_window_spacing_multiplier) / total_length
    intervals: list[tuple[float, float]] = []
    for i in range(1, len(path) - 1):
        if turn_angles[i] < corner_angle_threshold_deg:
            continue
        intervals.append((max(0.0, t_norm[i] - half_window), min(1.0, t_norm[i] + half_window)))
    if not intervals:
        return []
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _is_in_intervals(t_value: float, intervals: list[tuple[float, float]]) -> bool:
    return any(start <= t_value <= end for start, end in intervals)


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-9:
        return np.zeros_like(vec)
    return vec / norm


def _rodrigues_rotate(vec: np.ndarray, axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = _normalize(axis)
    if float(np.linalg.norm(axis)) <= 1e-9:
        return vec
    cos_a = float(np.cos(angle_rad))
    sin_a = float(np.sin(angle_rad))
    return (
        vec * cos_a
        + np.cross(axis, vec) * sin_a
        + axis * np.dot(axis, vec) * (1.0 - cos_a)
    )


def _interp_full_point(start: np.ndarray, end: np.ndarray, ratio: float) -> list[float]:
    ratio = float(np.clip(ratio, 0.0, 1.0))
    return (start + ratio * (end - start)).tolist()


def blend_corners_with_radius(
    path: list[list[float]],
    blend_radius_mm: float,
    target_spacing_mm: float,
    corner_angle_threshold_deg: float = 35.0,
) -> list[list[float]]:
    """Replace sharp corners with local circular blends in robot space."""
    if len(path) < 3 or blend_radius_mm <= 1e-6:
        return [list(point) for point in path]

    points = np.array(path, dtype=float)
    n = len(points)
    corner_specs: dict[int, dict] = {}

    for i in range(1, n - 1):
        prev_pt = points[i - 1]
        curr_pt = points[i]
        next_pt = points[i + 1]

        prev_vec = curr_pt[:3] - prev_pt[:3]
        next_vec = next_pt[:3] - curr_pt[:3]
        prev_len = float(np.linalg.norm(prev_vec))
        next_len = float(np.linalg.norm(next_vec))
        if prev_len <= 1e-6 or next_len <= 1e-6:
            continue

        u_in = prev_vec / prev_len
        u_out = next_vec / next_len
        turn_angle_deg = float(np.degrees(np.arccos(np.clip(np.dot(u_in, u_out), -1.0, 1.0))))
        if turn_angle_deg < corner_angle_threshold_deg or turn_angle_deg > 175.0:
            continue

        theta = float(np.radians(turn_angle_deg))
        trim_dist = float(blend_radius_mm * np.tan(theta / 2.0))
        trim_dist = min(trim_dist, prev_len * 0.45, next_len * 0.45)
        if trim_dist <= 1e-6:
            continue

        effective_radius = float(trim_dist / np.tan(theta / 2.0))
        tangent_in_ratio = 1.0 - (trim_dist / prev_len)
        tangent_out_ratio = trim_dist / next_len

        tangent_in = np.array(_interp_full_point(prev_pt, curr_pt, tangent_in_ratio), dtype=float)
        tangent_out = np.array(_interp_full_point(curr_pt, next_pt, tangent_out_ratio), dtype=float)

        bisector = _normalize(u_out - u_in)
        normal = np.cross(u_in, u_out)
        if float(np.linalg.norm(bisector)) <= 1e-6 or float(np.linalg.norm(normal)) <= 1e-6:
            continue

        center = curr_pt[:3] + bisector * (effective_radius / max(np.sin(theta / 2.0), 1e-6))
        va = tangent_in[:3] - center
        vb = tangent_out[:3] - center
        signed_angle = float(np.arctan2(np.dot(np.cross(va, vb), normal), np.dot(va, vb)))
        if abs(signed_angle) <= 1e-6:
            continue

        arc_length = abs(signed_angle) * effective_radius
        arc_steps = max(2, int(np.ceil(arc_length / max(target_spacing_mm, 1e-6))))
        arc_points: list[list[float]] = []
        for step in range(arc_steps + 1):
            ratio = step / arc_steps
            angle = signed_angle * ratio
            rotated = center + _rodrigues_rotate(va, normal, angle)
            full_point = tangent_in + ratio * (tangent_out - tangent_in)
            full_point[:3] = rotated
            arc_points.append(full_point.tolist())

        corner_specs[i] = {
            "tangent_in": tangent_in.tolist(),
            "tangent_out": tangent_out.tolist(),
            "arc_points": arc_points,
        }

    if not corner_specs:
        return [list(point) for point in path]

    blended: list[list[float]] = [points[0].tolist()]
    for seg_idx in range(n - 1):
        start_point = corner_specs[seg_idx]["tangent_out"] if seg_idx in corner_specs else points[seg_idx].tolist()
        end_point = corner_specs[seg_idx + 1]["tangent_in"] if (seg_idx + 1) in corner_specs else points[seg_idx + 1].tolist()

        if any(abs(float(a) - float(b)) > 1e-9 for a, b in zip(blended[-1], start_point)):
            blended.append(start_point)
        if any(abs(float(a) - float(b)) > 1e-9 for a, b in zip(blended[-1], end_point)):
            blended.append(end_point)

        if (seg_idx + 1) in corner_specs:
            for point in corner_specs[seg_idx + 1]["arc_points"][1:]:
                if any(abs(float(a) - float(b)) > 1e-9 for a, b in zip(blended[-1], point)):
                    blended.append(point)

    return blended


def _blend_corner_only_path(
    original_path: list[list[float]],
    dense_linear: list[list[float]],
    smoothed: list[list[float]],
    target_spacing_mm: float,
    corner_angle_threshold_deg: float = 35.0,
    corner_window_spacing_multiplier: float = 3.0,
) -> list[list[float]]:
    intervals = _build_corner_intervals(
        original_path,
        target_spacing_mm=target_spacing_mm,
        corner_angle_threshold_deg=corner_angle_threshold_deg,
        corner_window_spacing_multiplier=corner_window_spacing_multiplier,
    )
    if not intervals:
        return original_path

    original_t, _ = _compute_normalized_arc_length(original_path)
    spline_t, _ = _compute_normalized_arc_length(smoothed)

    merged_points: list[tuple[float, list[float]]] = []
    for t_value, point in zip(original_t, original_path):
        if not _is_in_intervals(float(t_value), intervals):
            merged_points.append((float(t_value), list(point)))
    for t_value, point in zip(spline_t, smoothed):
        if _is_in_intervals(float(t_value), intervals):
            merged_points.append((float(t_value), list(point)))

    merged_points.append((0.0, list(original_path[0])))
    merged_points.append((1.0, list(original_path[-1])))
    merged_points.sort(key=lambda item: item[0])

    result: list[list[float]] = []
    for _, point in merged_points:
        if not result or any(abs(float(a) - float(b)) > 1e-9 for a, b in zip(result[-1], point)):
            result.append(point)
    return result


def _stage_linear_densification(
    path: list[list[float]],
    adaptive_spacing_mm: float,
    debug: bool,
) -> list[list[float]]:
    """Stage 1: Densify the path by inserting linearly interpolated points.

    Adds intermediate points between each pair of original vertices so that
    the subsequent spline stage has enough data to produce a smooth curve.

    Args:
        path: Original sparse path (list of [x, y, z, rx_degrees, ry_degrees, rz_degrees] points).
        adaptive_spacing_mm: Target distance between consecutive points in mm.
        debug: If True, print progress information.

    Returns:
        Densified path with more points at approximately *adaptive_spacing_mm*
        apart.
    """
    if debug:
        print(f"Stage 1: Linear densification from {len(path)} points...")

    path_array = np.array(path, dtype=float)
    turn_angles = _compute_turn_angles_deg(path)
    dense: list[list[float]] = []
    segments_interpolated = 0
    segments_skipped = 0

    for i in range(len(path_array) - 1):
        start = path_array[i]
        end = path_array[i + 1]
        dense.append(start.tolist())

        local_turn = max(float(turn_angles[i]), float(turn_angles[i + 1]))
        is_corner_segment = local_turn >= 35.0
        local_spacing = adaptive_spacing_mm / 3.0 if is_corner_segment else adaptive_spacing_mm

        seg_length = float(np.linalg.norm(end[:3] - start[:3]))
        if seg_length < (local_spacing * 2.0):
            segments_skipped += 1
            continue

        num_intermediate = int(np.floor(seg_length / local_spacing))
        if num_intermediate <= 0:
            segments_skipped += 1
            continue

        segments_interpolated += 1
        for j in range(1, num_intermediate + 1):
            t = j / (num_intermediate + 1)
            point = start + t * (end - start)
            dense.append(point.tolist())

    dense.append(path_array[-1].tolist())

    if debug:
        print(f"  -> {len(dense)} dense points")
        print(
            f"  -> segments interpolated: {segments_interpolated}, skipped: {segments_skipped}, "
            f"corner spacing={adaptive_spacing_mm / 3.0:.2f}mm"
        )

    return dense


def _stage_spline_smoothing(
    dense_path: list[list[float]],
    original_path: list[list[float]],
    adaptive_spacing_mm: float,
    spline_density_multiplier: float,
    smoothing_lambda: float,
    debug: bool,
    blend_radius_mm: float | None = None,
    pre_smooth_max_deviation_mm: float = 1.0,
) -> list[list[float]]:
    """Stage 2: Apply local corner blending in robot space."""
    if debug:
        print(
            "Stage 2: Corner blending "
            f"(density multiplier: {spline_density_multiplier}x, lambda={smoothing_lambda})..."
        )

    blend_spacing = adaptive_spacing_mm / spline_density_multiplier
    effective_blend_radius_mm = (
        float(blend_radius_mm)
        if blend_radius_mm is not None and float(blend_radius_mm) > 0.0
        else max(blend_spacing, adaptive_spacing_mm * 0.5)
    )
    smoothed = blend_corners_with_radius(
        original_path,
        blend_radius_mm=effective_blend_radius_mm,
        target_spacing_mm=blend_spacing,
    )
    smoothed = pre_smooth_path_for_interpolation(
        smoothed,
        window_size=3,
        passes=1,
        preserve_corner_angle_deg=20.0,
        max_deviation_mm=pre_smooth_max_deviation_mm,
    )

    if debug:
        print(
            f"  -> {len(smoothed)} final blended points "
            f"(radius={effective_blend_radius_mm:.2f}mm, post-smooth-dev={pre_smooth_max_deviation_mm:.2f}mm)"
        )

    return smoothed


def interpolate_path_two_stage(
    path: list[list[float]],
    adaptive_spacing_mm: float,
    spline_density_multiplier: float = 2.0,
    smoothing_lambda: float = 0.0,
    debug: bool = False,
    return_pre_smoothed: bool = False,
    blend_radius_mm: float | None = None,
    pre_smooth_max_deviation_mm: float = 1.0,
):
    """Two-stage path interpolation: linear densification then spline smoothing.

    Stage 1 inserts linearly spaced points so that the original coarse path
    has enough density for a reliable spline fit.  Stage 2 fits a cubic spline
    and re-samples at an even finer spacing to produce a smooth trajectory.

    Args:
        path: Input path as a list of N points, each point is a list of floats
            (e.g. [x, y, z, rx_degrees, ry_degrees, rz_degrees]).
        adaptive_spacing_mm: Target distance between consecutive points in mm
            for the linear densification stage.
        spline_density_multiplier: Controls how much denser the spline output
            is relative to the linear stage.  Output spacing =
            ``adaptive_spacing_mm / spline_density_multiplier``.
        smoothing_lambda: Smoothing factor for the spline stage.
            0.0 = exact interpolation; larger values produce smoother curves
            that may deviate from the input points.
        debug: If True, print progress information for both stages.

    Returns:
        A tuple of (dense_linear, smoothed) where:
            - dense_linear: Path after stage 1 (linear densification only).
            - smoothed: Path after stage 2 (spline smoothing).
    """
    if len(path) < 2:
        if return_pre_smoothed:
            return path, path, path
        return path, path

    pre_smoothed = pre_smooth_path_for_interpolation(path)

    if debug:
        print(f"Stage 0: Pre-smoothing from {len(path)} points...")

    dense_linear = _stage_linear_densification(pre_smoothed, adaptive_spacing_mm, debug)

    if len(dense_linear) < 4:
        if debug:
            print(f"  -> Skipping spline stage (need >= 4 points, have {len(dense_linear)})")
        if return_pre_smoothed:
            return pre_smoothed, dense_linear, dense_linear
        return dense_linear, dense_linear

    smoothed = _stage_spline_smoothing(
        dense_linear,
        pre_smoothed,
        adaptive_spacing_mm,
        spline_density_multiplier,
        smoothing_lambda,
        debug,
        blend_radius_mm=blend_radius_mm,
        pre_smooth_max_deviation_mm=pre_smooth_max_deviation_mm,
    )

    if return_pre_smoothed:
        return pre_smoothed, dense_linear, smoothed
    return dense_linear, smoothed

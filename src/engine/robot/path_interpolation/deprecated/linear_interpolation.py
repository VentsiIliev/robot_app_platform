import numpy as np
import numpy.typing as npt


def _lerp_points(start: npt.NDArray, end: npt.NDArray, num_points: int) -> list[list[float]]:
    """Generate *num_points* evenly spaced points between start and end (exclusive of both)."""
    points = []
    for j in range(1, num_points + 1):
        t = j / (num_points + 1)
        point = start + t * (end - start)
        points.append(point.tolist())
    return points

def _interpolate_segment_adaptive(start: npt.NDArray, end: npt.NDArray, target_spacing_mm: float) -> tuple[list[list[float]], bool]:
    """Interpolate a single segment using adaptive spacing.

    Returns (intermediate_points, was_interpolated).
    If the segment is too short (< 2x target spacing), no points are added.
    """
    segment_length = np.linalg.norm(end[:3] - start[:3])

    # Only interpolate if segment is at least 2x the target spacing.
    # This ensures at least 2 evenly spaced intervals (start -> mid -> end).
    # Example: spacing=50mm, segment=70mm would create uneven 50mm+20mm — better to skip.
    if segment_length < (target_spacing_mm * 2):
        return [], False

    num_intermediate = int(np.floor(segment_length / target_spacing_mm))
    return _lerp_points(start, end, num_intermediate), True


def _log_debug(path_len: int, result_len: int, target_spacing_mm: float, segments_interpolated: int, segments_skipped: int) -> None:
    """Print interpolation summary when debug is enabled."""
    print(f"Adaptive linear interpolation: {path_len} → {result_len} points")
    print(f"  Target spacing: {target_spacing_mm}mm")
    print(f"  Segments interpolated: {segments_interpolated}, skipped: {segments_skipped} (too short)")

def interpolate_path_linear(path: list[list[float]], target_spacing_mm: float, debug: bool = False) -> list[list[float]]:

    if len(path) < 2:
        return path

    path_array = np.array(path)
    num_points = len(path)
    interpolated_path = []

    segments_interpolated = 0
    segments_skipped = 0

    for i in range(num_points - 1):
        start = path_array[i]
        end = path_array[i + 1]

        interpolated_path.append(start.tolist())

        points, was_interpolated = _interpolate_segment_adaptive(start, end, target_spacing_mm)
        if was_interpolated:
            segments_interpolated += 1
            interpolated_path.extend(points)
        else:
            segments_skipped += 1

    interpolated_path.append(path_array[-1].tolist())

    if debug:
        _log_debug(len(path), len(interpolated_path), target_spacing_mm,
                   segments_interpolated, segments_skipped)

    return interpolated_path
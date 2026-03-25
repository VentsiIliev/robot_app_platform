import numpy as np
import numpy.typing as npt


def _compute_arc_length_parameterization(path_array: npt.NDArray) -> tuple[npt.NDArray, float]:
    """Compute a normalized arc-length parameter for each point in the path.

    Arc-length parameterization maps each point to a value in [0, 1] based on
    its cumulative distance along the path (using only x, y, z coordinates).
    This avoids distortions that occur when parameterizing by point index,
    especially when segments have very different lengths.

    Args:
        path_array: Array of shape (N, D) where the first 3 columns are x, y, z.

    Returns:
        t: Normalized parameter array of shape (N,) with values in [0, 1].
        total_length: Total arc length of the path in mm.
    """
    diffs = np.diff(path_array[:, :3], axis=0)
    segment_lengths = np.linalg.norm(diffs, axis=1)
    cumulative_length = np.concatenate([[0], np.cumsum(segment_lengths)])

    total_length = float(cumulative_length[-1])
    t = cumulative_length / total_length

    return t, total_length


def _compute_sample_count(n_original: int, total_length: float, target_spacing_mm: float) -> int:
    """Decide how many output points the spline should be sampled at.

    Uses whichever is larger:
      - twice the original point count (guarantees the spline is at least as
        dense as the input), or
      - the number of evenly spaced samples needed to achieve
        *target_spacing_mm* along the path.

    Args:
        n_original: Number of points in the input path.
        total_length: Total arc length of the path in mm.
        target_spacing_mm: Desired spacing between output points in mm.

    Returns:
        The number of sample points for the output spline.
    """
    return max(n_original * 2, int(np.ceil(total_length / target_spacing_mm)))


def _fit_spline_dimension(
    t: npt.NDArray,
    values: npt.NDArray,
    t_new: npt.NDArray,
    k: int,
    smoothing_lambda: float,
    dim_index: int,
) -> npt.NDArray:
    """Fit a univariate spline to one dimension and evaluate at new parameters.

    If the spline fit fails (e.g., due to numerical issues), falls back to
    simple linear interpolation so the pipeline never crashes.

    Args:
        t: Normalized arc-length parameters for the input points, shape (N,).
        values: Coordinate values for this dimension, shape (N,).
        t_new: Parameters at which to evaluate the spline, shape (M,).
        k: Degree of the spline (1=linear, 2=quadratic, 3=cubic).
        smoothing_lambda: Smoothing factor passed to ``UnivariateSpline(s=...)``.
            0.0 means exact interpolation (passes through every point);
            larger values allow the spline to deviate for a smoother result.
        dim_index: Index of the dimension (used only for the warning message).

    Returns:
        Interpolated values at *t_new*, shape (M,).
    """
    try:
        from scipy.interpolate import UnivariateSpline
        spline = UnivariateSpline(t, values, k=k, s=smoothing_lambda)
        return spline(t_new)
    except Exception as e:
        print(f"spline dim {dim_index} failed, fallback to linear: {e}")
        return np.interp(t_new, t, values)


def interpolate_path_spline_with_lambda(
    path: list[list[float]],
    target_spacing_mm: float = 5.0,
    k: int = 3,
    smoothing_lambda: float = 0.0,
) -> list[list[float]]:
    """Smooth a path using univariate splines with arc-length parameterization.

    Each coordinate dimension (x, y, z, rx_degrees, ry_degrees, rz_degrees, ...) is fitted with an
    independent ``UnivariateSpline``.  The spline is then sampled at evenly spaced arc-length intervals to produce the output path.

    Args:
        path: Input path as a list of N points, each point is a list of floats
            (e.g. [x, y, z, rx_degrees, ry_degrees, rz_degrees]).
        target_spacing_mm: Desired distance between consecutive output points
            in mm.  Smaller values produce denser output.
        k: Degree of the spline curve (1=linear, 2=quadratic, 3=cubic).
            Must satisfy ``len(path) >= k + 1``.
        smoothing_lambda: Smoothing factor for ``UnivariateSpline(s=...)``.
            0.0 = exact interpolation (a curve passes through every input point).
            Increasing this allows the curve to deviate from the input points
            for a smoother result.

    Returns:
        Smoothed path as a list of M points with the same dimensionality as
        the input.
    """
    if len(path) < k + 1:
        return path

    path_array = np.array(path)

    t, total_length = _compute_arc_length_parameterization(path_array)
    if total_length <= 0:
        return path

    # Remove coincident points: duplicate t values make UnivariateSpline(s=0) crash.
    # np.unique returns the first occurrence of each unique value in sorted order.
    _, unique_idx = np.unique(t, return_index=True)
    if len(unique_idx) < len(t):
        path_array = path_array[unique_idx]
        t = t[unique_idx]
        if len(t) < k + 1:
            return path

    total_points = _compute_sample_count(len(path_array), total_length, target_spacing_mm)
    t_new = np.linspace(0, 1, total_points)

    interpolated_dims = []
    for dim in range(path_array.shape[1]):
        interpolated_dims.append(
            _fit_spline_dimension(t, path_array[:, dim], t_new, k, smoothing_lambda, dim)
        )

    return np.column_stack(interpolated_dims).tolist()
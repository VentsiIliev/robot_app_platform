from src.engine.robot.path_interpolation.linear_interpolation import interpolate_path_linear
from src.engine.robot.path_interpolation.spline_interpolation import interpolate_path_spline_with_lambda


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

    dense = interpolate_path_linear(path, target_spacing_mm=adaptive_spacing_mm, debug=debug)

    if debug:
        print(f"  -> {len(dense)} dense points")

    return dense


def _stage_spline_smoothing(
    dense_path: list[list[float]],
    adaptive_spacing_mm: float,
    spline_density_multiplier: float,
    smoothing_lambda: float,
    debug: bool,
) -> list[list[float]]:
    """Stage 2: Smooth the densified path with a cubic spline.

    Fits independent univariate splines per dimension and re-samples at a
    finer spacing than the linear stage (controlled by
    *spline_density_multiplier*).

    Args:
        dense_path: Densified path produced by stage 1.
        adaptive_spacing_mm: Base spacing from stage 1, used together with
            *spline_density_multiplier* to compute the spline output spacing.
        spline_density_multiplier: The spline output spacing is
            ``adaptive_spacing_mm / spline_density_multiplier``.  Higher values
            produce denser, smoother output.
        smoothing_lambda: Smoothing factor for ``UnivariateSpline(s=...)``.
            0.0 = exact interpolation; larger values allow deviation for
            smoother results.
        debug: If True, print progress information.

    Returns:
        Smoothed path.
    """
    if debug:
        print(f"Stage 2: Spline smoothing (density multiplier: {spline_density_multiplier}x, lambda={smoothing_lambda})...")

    spline_spacing = adaptive_spacing_mm / spline_density_multiplier
    smoothed = interpolate_path_spline_with_lambda(
        dense_path,
        target_spacing_mm=spline_spacing,
        k=3,
        smoothing_lambda=smoothing_lambda,
    )

    if debug:
        print(f"  -> {len(smoothed)} final smooth points")

    return smoothed


def interpolate_path_two_stage(
    path: list[list[float]],
    adaptive_spacing_mm: float,
    spline_density_multiplier: float = 2.0,
    smoothing_lambda: float = 0.0,
    debug: bool = False,
) -> tuple[list[list[float]], list[list[float]]]:
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
        return path, path

    dense_linear = _stage_linear_densification(path, adaptive_spacing_mm, debug)

    if len(dense_linear) < 4:
        if debug:
            print(f"  -> Skipping spline stage (need >= 4 points, have {len(dense_linear)})")
        return dense_linear, dense_linear

    smoothed = _stage_spline_smoothing(
        dense_linear, adaptive_spacing_mm, spline_density_multiplier, smoothing_lambda, debug
    )

    return dense_linear, smoothed
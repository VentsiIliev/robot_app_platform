# `src/engine/robot/path_interpolation/` — Path Interpolation

Utility functions for densifying and smoothing robot motion paths. Used when a coarse list of waypoints needs to be converted into a finer trajectory for smoother robot motion.

---

## Files

| File | Purpose |
|------|---------|
| `linear_interpolation.py` | `interpolate_path_linear()` — adaptive linear densification |
| `spline_interpolation.py` | `interpolate_path_spline_with_lambda()` — cubic spline smoothing with arc-length parameterisation |
| `combined_interpolation.py` | `interpolate_path_two_stage()` — linear densification then spline smoothing |
| `debug_plotting.py` | Matplotlib debug visualisation (not used in production) |

---

## `interpolate_path_linear()`

```python
def interpolate_path_linear(
    path: list[list[float]],
    target_spacing_mm: float,
    debug: bool = False,
) -> list[list[float]]:
```

Inserts linearly interpolated intermediate points between each pair of consecutive path vertices so that the output has approximately `target_spacing_mm` between consecutive points.

**Segment skip rule** — a segment is only interpolated if its length is at least `2 × target_spacing_mm`. Shorter segments are left as-is to avoid uneven spacing (e.g. a 70 mm segment with 50 mm spacing would produce 50+20 mm — worse than skipping).

Input/output format: each point is `[x, y, z, rx_degrees, ry_degrees, rz_degrees, ...]`. Distance is computed from the first three coordinates (XYZ) only.

---

## `interpolate_path_spline_with_lambda()`

```python
def interpolate_path_spline_with_lambda(
    path: list[list[float]],
    target_spacing_mm: float = 5.0,
    k: int = 3,
    smoothing_lambda: float = 0.0,
) -> list[list[float]]:
```

Fits an independent `scipy.interpolate.UnivariateSpline` per coordinate dimension and re-samples at evenly spaced arc-length intervals.

| Parameter | Effect |
|-----------|--------|
| `k` | Spline degree: 1=linear, 2=quadratic, **3=cubic** (default) |
| `smoothing_lambda` | `s=` parameter for `UnivariateSpline`. `0.0` = exact interpolation (curve passes through every point). Larger values produce smoother curves that may deviate from input points. |

**Arc-length parameterisation** — parameterises the spline by cumulative XYZ distance rather than point index. This prevents distortion when path segments have very different lengths.

**Coincident-point handling** — duplicate arc-length parameter values (from coincident points) cause `UnivariateSpline(s=0)` to crash. The implementation deduplicates via `np.unique` before fitting.

**Fallback** — if a single dimension's spline fails numerically, falls back to `np.interp` (linear interpolation) for that dimension so the pipeline never crashes.

---

## `interpolate_path_two_stage()`

```python
def interpolate_path_two_stage(
    path: list[list[float]],
    adaptive_spacing_mm: float,
    spline_density_multiplier: float = 2.0,
    smoothing_lambda: float = 0.0,
    debug: bool = False,
) -> tuple[list[list[float]], list[list[float]]]:
```

Combines both stages and returns `(dense_linear, smoothed)`:

1. **Stage 1** — `interpolate_path_linear(path, adaptive_spacing_mm)` — densifies the coarse input so the spline stage has sufficient data
2. **Stage 2** — `interpolate_path_spline_with_lambda(dense, adaptive_spacing_mm / spline_density_multiplier)` — fits and re-samples at `spline_density_multiplier` times finer spacing

Stage 2 is skipped if the densified path has fewer than 4 points (minimum for a cubic spline).

| Parameter | Default | Effect |
|-----------|---------|--------|
| `spline_density_multiplier` | `2.0` | Output spacing = `adaptive_spacing_mm / multiplier`. Higher = denser, smoother output |
| `smoothing_lambda` | `0.0` | Passed to the spline stage; 0 = exact |

---

## Usage Example

```python
from src.engine.robot.path_interpolation.combined_interpolation import interpolate_path_two_stage

coarse_path = [[0, 0, 100, 180, 0, 0], [100, 0, 100, 180, 0, 0], [100, 100, 100, 180, 0, 0]]
dense, smooth = interpolate_path_two_stage(coarse_path, adaptive_spacing_mm=10.0)
# dense: linearly interpolated at ~10 mm spacing
# smooth: cubic spline at ~5 mm spacing
```

---

## Design Notes

- **XYZ-only distance** — all distance calculations use only the first three coordinates. Orientation dimensions are interpolated algebraically but don't affect spacing decisions.
- **Input unchanged** — both functions always return new lists; the input path is never mutated.
- **`debug=True`** — prints stage summaries to stdout; intended for development use only.

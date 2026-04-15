
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.signal import savgol_filter

try:
    from ruckig import InputParameter, OutputParameter, Result, Ruckig
    HAS_RUCKIG = True
except Exception:
    HAS_RUCKIG = False


CurveMethod = Literal["linear", "pchip",]
NoiseMethod = Literal["none", "moving_average", "savgol"]
ContourSelectionMode = Literal["largest_area", "index"]


@dataclass(slots=True)
class PreprocessConfig:
    close_tol: float = 5.0
    min_spacing: float = 1.0
    use_approx_poly_dp: bool = False
    approx_epsilon_factor: float = 0.01
    noise_method: NoiseMethod = "none"
    noise_strength: float = 5.0


@dataclass(slots=True)
class InterpolationConfig:
    method: CurveMethod = "pchip"
    output_spacing: float = 10.0
    dense_sampling_factor: float = 0.25


@dataclass(slots=True)
class RuckigConfig:
    enabled: bool = False
    dt: float = 0.01
    max_velocity: float = 200.0
    max_acceleration: float = 500.0
    max_jerk: float = 2000.0


@dataclass(slots=True)
class PipelineResult:
    raw: np.ndarray
    prepared: np.ndarray
    curve: np.ndarray
    sampled: np.ndarray
    profiles: dict[str, np.ndarray]
    ruckig: dict[str, np.ndarray] | None = None


def contour_to_xy(contour: np.ndarray) -> np.ndarray:
    """Convert a contour from OpenCV-style or Nx2 format to float Nx2."""
    arr = np.asarray(contour)
    if arr.ndim == 3 and arr.shape[1] == 1 and arr.shape[2] >= 2:
        arr = arr[:, 0, :2]
    elif arr.ndim == 2 and arr.shape[1] >= 2:
        arr = arr[:, :2]
    else:
        raise ValueError(f"Unsupported contour shape: {arr.shape}")
    return np.asarray(arr, dtype=float)


def normalize_contours(contours: list[np.ndarray] | None) -> list[np.ndarray]:
    """Normalize a list of contours into float Nx2 arrays."""
    if not contours:
        return []
    normalized: list[np.ndarray] = []
    for contour in contours:
        try:
            xy = contour_to_xy(contour)
            if len(xy) >= 2:
                normalized.append(xy)
        except Exception:
            continue
    return normalized


def contour_area_xy(contour: np.ndarray) -> float:
    """Compute absolute contour area in XY space."""
    if len(contour) < 3:
        return 0.0
    return float(abs(cv2.contourArea(contour.astype(np.float32).reshape(-1, 1, 2))))


def select_contour(
    contours: list[np.ndarray],
    mode: ContourSelectionMode = "largest_area",
    index: int = 0,
) -> np.ndarray:
    """Select one contour from a list."""
    if not contours:
        raise ValueError("No contours available.")
    if mode == "largest_area":
        areas = [contour_area_xy(c) for c in contours]
        return contours[int(np.argmax(areas))]
    if not (0 <= index < len(contours)):
        raise IndexError(f"Contour index out of range: {index}")
    return contours[index]


def remove_duplicate_consecutive(points: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    """Drop consecutive duplicates or near-duplicates."""
    if len(points) == 0:
        return points.copy()
    keep = [0]
    for i in range(1, len(points)):
        if np.linalg.norm(points[i] - points[keep[-1]]) > eps:
            keep.append(i)
    return points[keep]


def close_if_needed(points: np.ndarray, close_tol: float) -> np.ndarray:
    """Append the first point if the contour is almost closed."""
    if len(points) < 3:
        return points.copy()
    if np.linalg.norm(points[0] - points[-1]) <= close_tol and np.linalg.norm(points[0] - points[-1]) > 1e-9:
        return np.vstack([points, points[:1]])
    return points


def simplify_min_spacing(points: np.ndarray, min_spacing: float) -> np.ndarray:
    """Keep points separated by at least min_spacing."""
    if len(points) < 2 or min_spacing <= 0:
        return points.copy()
    out = [points[0]]
    for point in points[1:]:
        if np.linalg.norm(point - out[-1]) >= min_spacing:
            out.append(point)
    if np.linalg.norm(out[-1] - points[-1]) > 1e-9:
        out.append(points[-1])
    return np.asarray(out, dtype=float)


def approx_polyline(points: np.ndarray, epsilon_factor: float, closed: bool) -> np.ndarray:
    """Simplify using OpenCV approxPolyDP with perimeter-scaled epsilon."""
    if len(points) < 3 or epsilon_factor <= 0:
        return points.copy()
    contour = points.astype(np.float32).reshape(-1, 1, 2)
    epsilon = float(epsilon_factor) * float(cv2.arcLength(contour, closed))
    approx = cv2.approxPolyDP(contour, epsilon, closed)
    return approx[:, 0, :].astype(float)


def smooth_points(points: np.ndarray, method: NoiseMethod, strength: float) -> np.ndarray:
    """Apply optional light denoising in XY space."""
    if len(points) < 5 or strength <= 0 or method == "none":
        return points.copy()

    pts = points.copy()
    closed = np.linalg.norm(pts[0] - pts[-1]) < 1e-9
    base = pts[:-1] if closed and len(pts) > 3 else pts

    if method == "moving_average":
        window = max(3, int(round(strength)))
        if window % 2 == 0:
            window += 1
        radius = window // 2
        padded = np.pad(base, ((radius, radius), (0, 0)), mode="wrap" if closed else "edge")
        smoothed = np.zeros_like(base)
        for i in range(len(base)):
            smoothed[i] = padded[i:i + window].mean(axis=0)
        if not closed:
            smoothed[0] = base[0]
            smoothed[-1] = base[-1]
    elif method == "savgol":
        window = max(5, int(round(strength)))
        if window % 2 == 0:
            window += 1
        max_window = len(base) if len(base) % 2 == 1 else len(base) - 1
        window = min(window, max_window)
        if window < 5:
            return pts.copy()
        mode = "wrap" if closed else "interp"
        x = savgol_filter(base[:, 0], window_length=window, polyorder=2, mode=mode)
        y = savgol_filter(base[:, 1], window_length=window, polyorder=2, mode=mode)
        smoothed = np.c_[x, y]
        if not closed:
            smoothed[0] = base[0]
            smoothed[-1] = base[-1]
    else:
        raise ValueError(f"Unknown smoothing method: {method}")

    if closed:
        return np.vstack([smoothed, smoothed[:1]])
    return smoothed


def path_lengths(points: np.ndarray) -> np.ndarray:
    """Cumulative arc length along a polyline."""
    if len(points) == 0:
        return np.zeros(0)
    if len(points) == 1:
        return np.array([0.0])
    diffs = np.diff(points, axis=0)
    segment_lengths = np.linalg.norm(diffs, axis=1)
    return np.concatenate([[0.0], np.cumsum(segment_lengths)])



def pchip_curve(points: np.ndarray, sample_count: int) -> np.ndarray:
    """Fit and sample a PCHIP curve using arc length as parameter."""
    pts = remove_duplicate_consecutive(points)
    s = path_lengths(pts)
    if float(s[-1]) <= 1e-9:
        return pts.copy()
    sx = PchipInterpolator(s, pts[:, 0])
    sy = PchipInterpolator(s, pts[:, 1])
    t = np.linspace(0.0, s[-1], max(20, int(sample_count)))
    return np.c_[sx(t), sy(t)]



def fit_curve(points: np.ndarray, config: InterpolationConfig) -> np.ndarray:
    """Create a dense geometric curve from prepared contour points."""
    closed = np.linalg.norm(points[0] - points[-1]) < 1e-9
    total_length = max(float(path_lengths(points)[-1]), 1.0)
    dense_samples = max(100, int(total_length / max(config.output_spacing * config.dense_sampling_factor, 0.5)))

    if config.method == "linear":
        return points.copy()
    if config.method == "pchip":
        return pchip_curve(points, dense_samples)

    raise ValueError(f"Unknown curve method: {config.method}")


def arc_length_resample(points: np.ndarray, spacing: float) -> np.ndarray:
    """Resample a polyline at nearly uniform arc-length spacing."""
    points = remove_duplicate_consecutive(points)
    if len(points) < 2:
        return points.copy()
    s = path_lengths(points)
    total = float(s[-1])
    if total <= 1e-9:
        return points[:1].copy()

    targets = list(np.arange(0.0, total, max(float(spacing), 1e-6)))
    if not targets or abs(targets[-1] - total) > 1e-9:
        targets.append(total)
    targets = np.asarray(targets, dtype=float)

    x = np.interp(targets, s, points[:, 0])
    y = np.interp(targets, s, points[:, 1])
    out = np.c_[x, y]

    if np.linalg.norm(points[0] - points[-1]) < 1e-9 and np.linalg.norm(out[0] - out[-1]) > 1e-6:
        out = np.vstack([out, out[:1]])
    return out


def compute_profiles(points: np.ndarray) -> dict[str, np.ndarray]:
    """Compute position, velocity, acceleration, and jerk-like XY profiles over arc length."""
    pts = remove_duplicate_consecutive(points)
    if len(pts) < 2:
        z = np.zeros(1)
        return {"t": z, "x": z, "y": z, "vx": z, "vy": z, "ax": z, "ay": z, "jx": z, "jy": z}

    t = path_lengths(pts)
    x = pts[:, 0]
    y = pts[:, 1]
    vx = np.gradient(x, t, edge_order=1)
    vy = np.gradient(y, t, edge_order=1)
    ax = np.gradient(vx, t, edge_order=1)
    ay = np.gradient(vy, t, edge_order=1)
    jx = np.gradient(ax, t, edge_order=1)
    jy = np.gradient(ay, t, edge_order=1)

    return {"t": t, "x": x, "y": y, "vx": vx, "vy": vy, "ax": ax, "ay": ay, "jx": jx, "jy": jy}


def apply_ruckig(points: np.ndarray, config: RuckigConfig) -> dict[str, np.ndarray]:
    """Run simple segment-by-segment Ruckig post-processing on XY points."""
    if not config.enabled:
        raise ValueError("Ruckig is disabled.")
    if not HAS_RUCKIG:
        raise RuntimeError("Ruckig not installed. Run: pip install ruckig")

    pts = remove_duplicate_consecutive(points)
    if len(pts) < 2:
        z = np.zeros(1)
        return {"points": pts.copy(), "t": z, "x": z, "y": z, "vx": z, "vy": z, "ax": z, "ay": z, "jx": z, "jy": z}

    otg = Ruckig(2, float(config.dt))
    inp = InputParameter(2)
    out = OutputParameter(2)

    inp.current_position = pts[0].tolist()
    inp.current_velocity = [0.0, 0.0]
    inp.current_acceleration = [0.0, 0.0]
    inp.max_velocity = [float(config.max_velocity), float(config.max_velocity)]
    inp.max_acceleration = [float(config.max_acceleration), float(config.max_acceleration)]
    inp.max_jerk = [float(config.max_jerk), float(config.max_jerk)]

    pos_list = [np.array(inp.current_position, dtype=float)]
    vel_list = [np.array(inp.current_velocity, dtype=float)]
    acc_list = [np.array(inp.current_acceleration, dtype=float)]
    time_list = [0.0]

    for waypoint in pts[1:]:
        inp.target_position = [float(waypoint[0]), float(waypoint[1])]
        inp.target_velocity = [0.0, 0.0]
        inp.target_acceleration = [0.0, 0.0]

        steps = 0
        while True:
            result = otg.update(inp, out)
            if result == Result.ErrorInvalidInput:
                raise RuntimeError("Ruckig rejected the target state.")
            if result not in (Result.Working, Result.Finished):
                raise RuntimeError(f"Ruckig failed with result {result}")

            pos_list.append(np.array(out.new_position, dtype=float))
            vel_list.append(np.array(out.new_velocity, dtype=float))
            acc_list.append(np.array(out.new_acceleration, dtype=float))
            time_list.append(time_list[-1] + float(config.dt))
            out.pass_to_input(inp)

            steps += 1
            if result == Result.Finished:
                break
            if steps > 200000:
                raise RuntimeError("Ruckig exceeded step budget.")

    pos = np.asarray(pos_list, dtype=float)
    vel = np.asarray(vel_list, dtype=float)
    acc = np.asarray(acc_list, dtype=float)
    t = np.asarray(time_list, dtype=float)
    jx = np.gradient(acc[:, 0], t, edge_order=1) if len(t) >= 2 else np.zeros(len(pos))
    jy = np.gradient(acc[:, 1], t, edge_order=1) if len(t) >= 2 else np.zeros(len(pos))

    return {
        "points": pos,
        "t": t,
        "x": pos[:, 0],
        "y": pos[:, 1],
        "vx": vel[:, 0],
        "vy": vel[:, 1],
        "ax": acc[:, 0],
        "ay": acc[:, 1],
        "jx": jx,
        "jy": jy,
    }


class ContourPathPipeline:
    """Clean contour-to-path pipeline for vision contours."""

    def __init__(
        self,
        preprocess: PreprocessConfig | None = None,
        interpolation: InterpolationConfig | None = None,
        ruckig: RuckigConfig | None = None,
    ) -> None:
        self.preprocess = preprocess or PreprocessConfig()
        self.interpolation = interpolation or InterpolationConfig()
        self.ruckig = ruckig or RuckigConfig()

    def prepare(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Normalize and preprocess raw contour points."""
        raw = remove_duplicate_consecutive(np.asarray(points, dtype=float))
        raw = close_if_needed(raw, self.preprocess.close_tol)

        prepared = raw.copy()
        if self.preprocess.use_approx_poly_dp:
            closed = np.linalg.norm(prepared[0] - prepared[-1]) < 1e-9
            prepared = approx_polyline(prepared, self.preprocess.approx_epsilon_factor, closed)

        prepared = simplify_min_spacing(prepared, self.preprocess.min_spacing)
        prepared = smooth_points(prepared, self.preprocess.noise_method, self.preprocess.noise_strength)
        return raw, prepared

    def run(self, points: np.ndarray) -> PipelineResult:
        """Run the full contour pipeline."""
        raw, prepared = self.prepare(points)
        curve = fit_curve(prepared, self.interpolation)
        sampled = arc_length_resample(curve, self.interpolation.output_spacing)
        profiles = compute_profiles(sampled)
        ruckig_result = apply_ruckig(sampled, self.ruckig) if self.ruckig.enabled else None
        return PipelineResult(
            raw=raw,
            prepared=prepared,
            curve=curve,
            sampled=sampled,
            profiles=profiles,
            ruckig=ruckig_result,
        )

from __future__ import annotations

import copy
import logging
import numpy as np
from scipy.spatial import cKDTree

DXF_ALIGNMENT_STRATEGY_RIGID = "rigid"
DXF_ALIGNMENT_STRATEGY_REFERENCE_SMOOTH = "reference_smooth"
DEFAULT_MAX_SCALE_DEVIATION = 0.03

_logger = logging.getLogger(__name__)


class _PoseScorer:
    """Cache transformed poses and target search structures during one alignment run."""

    def __init__(self, source_points: np.ndarray, target_points: np.ndarray, source_centroid: np.ndarray, overlap_fn):
        self._source_points = np.asarray(source_points, dtype=np.float64)
        self._target_points = np.asarray(target_points, dtype=np.float64)
        self._source_centroid = np.asarray(source_centroid, dtype=np.float64)
        self._overlap_fn = overlap_fn
        self._target_tree = _build_kdtree(self._target_points)
        self._source_tree = _build_kdtree(self._source_points)
        self._cache: dict[tuple[float, float, float, float], np.ndarray] = {}

    @property
    def target_tree(self) -> cKDTree | None:
        return self._target_tree

    @property
    def source_tree(self) -> cKDTree | None:
        return self._source_tree

    def transformed(self, theta: float, scale: float, translation: np.ndarray) -> np.ndarray:
        tx, ty = float(translation[0]), float(translation[1])
        key = (round(float(theta), 12), round(float(scale), 12), round(tx, 9), round(ty, 9))
        cached = self._cache.get(key)
        if cached is None:
            cached = _transform_points(
                self._source_points,
                self._source_centroid,
                theta,
                scale,
                np.asarray([tx, ty], dtype=np.float64),
            )
            self._cache[key] = cached
        return cached

    def symmetric_error(self, theta: float, scale: float, translation: np.ndarray) -> float:
        transformed = self.transformed(theta, scale, translation)
        return _symmetric_alignment_error(
            transformed,
            self._target_points,
            target_tree=self._target_tree,
            source_tree=self._source_tree,
        )

    def overlap(self, theta: float, scale: float, translation: np.ndarray) -> float:
        transformed = self.transformed(theta, scale, translation)
        return float(self._overlap_fn(transformed, self._target_points))

    def score(self, theta: float, scale: float, translation: np.ndarray) -> float:
        transformed = self.transformed(theta, scale, translation)
        overlap = float(self._overlap_fn(transformed, self._target_points))
        chamfer_like = _symmetric_alignment_error(
            transformed,
            self._target_points,
            target_tree=self._target_tree,
            source_tree=self._source_tree,
        )
        return overlap - 0.35 * chamfer_like


def align_raw_workpiece_to_contour(
    raw: dict,
    captured_contour,
    *,
    strategy: str = DXF_ALIGNMENT_STRATEGY_RIGID,
    max_scale_deviation: float | None = DEFAULT_MAX_SCALE_DEVIATION,
    reference_scale_override: float | None = None,
) -> dict:
    """Align a saved raw workpiece contour set onto a newly captured contour in image space."""
    from src.engine.vision.implementation.VisionSystem.features.contour_matching.utils import calculate_mask_overlap

    aligned = copy.deepcopy(raw)
    source_points = _extract_raw_contour_points(aligned)
    target_points = _normalize_contour_points(captured_contour)
    _logger.info(
        "[ALIGN] start strategy=%s max_scale_deviation=%s reference_scale_override=%s source=%s target=%s",
        str(strategy or DXF_ALIGNMENT_STRATEGY_RIGID).strip().lower(),
        None if max_scale_deviation is None else float(max_scale_deviation),
        None if reference_scale_override is None else float(reference_scale_override),
        _describe_contour(source_points),
        _describe_contour(target_points),
    )
    if len(source_points) < 3 or len(target_points) < 3:
        _logger.warning(
            "[ALIGN] skipped: insufficient points source_count=%d target_count=%d",
            len(source_points),
            len(target_points),
        )
        return aligned

    # Dense resampling reduces bias from unevenly spaced source vertices and
    # gives the later local search enough geometric resolution to converge.
    sample_count = 360
    source_resampled = _resample_closed_path(source_points, sample_count)
    target_resampled = _resample_closed_path(target_points, sample_count)
    if len(source_resampled) < 3 or len(target_resampled) < 3:
        return aligned

    source_centroid = np.mean(source_resampled, axis=0)

    # Stronger initialization than PCA-only:
    # search cyclic contour correspondences and both winding directions.
    best_theta, best_scale, best_translation = _best_initial_pose(
        source_resampled,
        target_resampled,
        num_shifts=64,
        max_scale_deviation=max_scale_deviation,
        reference_scale_override=reference_scale_override,
    )

    # Small ICP-style refinement to sharpen the pose before local scoring.
    best_theta, best_scale, best_translation = _refine_pose_icp(
        source_resampled,
        target_resampled,
        source_centroid,
        best_theta,
        best_scale,
        best_translation,
        iterations=8,
        trim_ratio=0.8,
        max_scale_deviation=max_scale_deviation,
        reference_scale_override=reference_scale_override,
    )

    # Final coarse-to-fine local refinement using a combined score:
    # overlap + symmetric contour distance.
    best_theta, best_scale, best_translation = _refine_alignment_with_mask_overlap(
        source_resampled,
        target_resampled,
        source_centroid,
        best_theta,
        best_scale,
        best_translation,
        calculate_mask_overlap,
        max_scale_deviation=max_scale_deviation,
        reference_scale_override=reference_scale_override,
    )

    _logger.info(
        "[ALIGN] solved theta_deg=%.3f scale=%.6f translation=(%.3f, %.3f) source_centroid=(%.3f, %.3f)",
        float(np.degrees(best_theta)),
        float(best_scale),
        float(best_translation[0]),
        float(best_translation[1]),
        float(source_centroid[0]),
        float(source_centroid[1]),
    )

    if str(strategy or DXF_ALIGNMENT_STRATEGY_RIGID).strip().lower() == DXF_ALIGNMENT_STRATEGY_REFERENCE_SMOOTH:
        _apply_reference_smoothed_main_contour(
            aligned,
            target_resampled,
            source_centroid,
            best_theta,
            best_scale,
            best_translation,
        )
    else:
        _transform_contour_in_place(
            _main_contour_payload(aligned),
            source_centroid,
            best_theta,
            best_scale,
            best_translation,
        )

    spray = aligned.get("sprayPattern") or {}
    for key in ("Contour", "Fill"):
        for segment in spray.get(key, []):
            _transform_contour_in_place(
                segment.get("contour"),
                source_centroid,
                best_theta,
                best_scale,
                best_translation,
            )
    _logger.info(
        "[ALIGN] result main=%s contour_segments=%d fill_segments=%d",
        _describe_contour(_extract_raw_contour_points(aligned)),
        len(spray.get("Contour", []) or []),
        len(spray.get("Fill", []) or []),
    )
    return aligned


def _describe_contour(points: np.ndarray) -> str:
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] < 2:
        return "count=0"
    pts = points[:, :2]
    mins = np.min(pts, axis=0)
    maxs = np.max(pts, axis=0)
    centroid = np.mean(pts, axis=0)
    area = _polygon_area(pts)
    return (
        f"count={len(pts)} "
        f"centroid=({float(centroid[0]):.3f}, {float(centroid[1]):.3f}) "
        f"bbox=({float(mins[0]):.3f}, {float(mins[1]):.3f})-({float(maxs[0]):.3f}, {float(maxs[1]):.3f}) "
        f"area={float(area):.3f}"
    )


def _main_contour_payload(raw: dict):
    """Return the raw main contour list, unwrapping compatibility wrapper payloads."""
    contour = (raw or {}).get("contour")
    if isinstance(contour, dict):
        nested = contour.get("contour")
        if nested is not None:
            return nested
    if contour is None:
        return []
    return contour


def _extract_raw_contour_points(raw: dict) -> np.ndarray:
    """Extract the main raw workpiece contour as an Nx2 numpy array."""
    contour = _main_contour_payload(raw)
    points: list[list[float]] = []
    for point in contour:
        if point is None:
            continue
        arr = np.asarray(point, dtype=np.float64)
        if arr.size < 2:
            continue
        flat = arr.reshape(-1)
        points.append([float(flat[0]), float(flat[1])])
    if not points:
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray(points, dtype=np.float64)


def _normalize_contour_points(contour) -> np.ndarray:
    """Normalize OpenCV-style contour arrays into a simple Nx2 float array."""
    array = np.asarray(contour, dtype=np.float64)
    if array.ndim == 3 and array.shape[1] == 1:
        array = array[:, 0, :]
    if array.ndim != 2 or array.shape[1] < 2:
        return np.empty((0, 2), dtype=np.float64)
    return array[:, :2]




def _resample_closed_path(points: np.ndarray, count: int) -> np.ndarray:
    """Resample a closed contour to a fixed number of evenly spaced points."""
    if len(points) < 2:
        return points

    closed_points = points
    if np.linalg.norm(points[0] - points[-1]) > 1e-6:
        closed_points = np.vstack([points, points[0]])

    segment_lengths = np.linalg.norm(np.diff(closed_points, axis=0), axis=1)
    total_length = float(np.sum(segment_lengths))
    if total_length <= 1e-9:
        return closed_points[:-1]

    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    samples = np.linspace(0.0, total_length, num=max(int(count), 3), endpoint=False)

    resampled = []
    seg_index = 0
    for sample in samples:
        while seg_index + 1 < len(cumulative) and cumulative[seg_index + 1] < sample:
            seg_index += 1

        seg_start = closed_points[seg_index]
        seg_end = closed_points[seg_index + 1]
        seg_len = segment_lengths[seg_index]

        if seg_len <= 1e-9:
            resampled.append(seg_start.copy())
            continue

        ratio = (sample - cumulative[seg_index]) / seg_len
        resampled.append(seg_start + ratio * (seg_end - seg_start))

    return np.asarray(resampled, dtype=np.float64)


def _principal_axis_angle(points: np.ndarray) -> float:
    """Estimate the dominant contour axis angle using PCA on the sampled points."""
    if len(points) < 2:
        return 0.0
    covariance = np.cov(points.T)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    axis = eigenvectors[:, int(np.argmax(eigenvalues))]
    return float(np.arctan2(axis[1], axis[0]))


def _rotation_matrix(theta: float) -> np.ndarray:
    """Construct a 2D rotation matrix."""
    return np.array(
        [
            [np.cos(theta), -np.sin(theta)],
            [np.sin(theta), np.cos(theta)],
        ],
        dtype=np.float64,
    )


def _rotate_and_scale_points(points: np.ndarray, center: np.ndarray, theta: float, scale: float) -> np.ndarray:
    """Rotate and uniformly scale points around a contour center."""
    rotation = _rotation_matrix(theta)
    return ((points - center) @ rotation.T) * float(scale) + center


def _transform_points(
    points: np.ndarray,
    center: np.ndarray,
    theta: float,
    scale: float,
    translation: np.ndarray,
) -> np.ndarray:
    """Apply rotation, uniform scale, and translation to a point cloud."""
    return _rotate_and_scale_points(points, center, theta, scale) + translation


def _bounding_box_size(points: np.ndarray) -> np.ndarray:
    """Return bounding-box width/height for an Nx2 contour."""
    if len(points) == 0:
        return np.array([0.0, 0.0], dtype=np.float64)
    mins = np.min(points, axis=0)
    maxs = np.max(points, axis=0)
    return np.asarray(maxs - mins, dtype=np.float64)


def _polygon_area(points: np.ndarray) -> float:
    """Return absolute polygon area for a closed contour sample."""
    if len(points) < 3:
        return 0.0
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _path_length(points: np.ndarray) -> float:
    """Return perimeter/closed path length for a contour sample."""
    if len(points) < 2:
        return 0.0
    closed = points if np.linalg.norm(points[0] - points[-1]) <= 1e-6 else np.vstack([points, points[0]])
    return float(np.sum(np.linalg.norm(np.diff(closed, axis=0), axis=1)))


def _robust_reference_scale(source_points: np.ndarray, target_points: np.ndarray) -> float:
    """
    Estimate a stable reference scale from several global contour measurements.

    Using the median of multiple shape-level ratios is more robust than trusting
    any single noisy metric or letting ICP drift the scale freely.
    """
    candidates: list[float] = []

    source_bbox = _bounding_box_size(source_points)
    target_bbox = _bounding_box_size(target_points)
    for source_dim, target_dim in zip(source_bbox, target_bbox):
        if float(source_dim) > 1e-9 and float(target_dim) > 1e-9:
            candidates.append(float(target_dim / source_dim))

    source_area = _polygon_area(source_points)
    target_area = _polygon_area(target_points)
    if source_area > 1e-9 and target_area > 1e-9:
        candidates.append(float(np.sqrt(target_area / source_area)))

    source_length = _path_length(source_points)
    target_length = _path_length(target_points)
    if source_length > 1e-9 and target_length > 1e-9:
        candidates.append(float(target_length / source_length))

    if not candidates:
        return 1.0
    return max(1e-3, float(np.median(np.asarray(candidates, dtype=np.float64))))


def _clamp_scale(scale: float, max_scale_deviation: float | None, reference_scale: float = 1.0) -> float:
    """Clamp scale around a reference value so noisy contours do not distort the DXF excessively."""
    scale = max(1e-3, float(scale))
    if max_scale_deviation is None:
        return scale
    deviation = max(0.0, float(max_scale_deviation))
    anchor = max(1e-3, float(reference_scale))
    return float(np.clip(scale, anchor * (1.0 - deviation), anchor * (1.0 + deviation)))


def _transform_contour_in_place(
    contour_array,
    center: np.ndarray,
    theta: float,
    scale: float,
    translation: np.ndarray,
) -> None:
    """Apply the solved similarity pose to a raw contour payload in place."""
    if contour_array is None:
        return
    for index, point in enumerate(contour_array):
        if point is None:
            continue
        arr = np.asarray(point, dtype=np.float64)
        if arr.size < 2:
            continue
        flat = arr.reshape(-1)
        vec = np.array([float(flat[0]), float(flat[1])], dtype=np.float64)
        mapped = _transform_points(
            vec[None, :],
            center,
            theta,
            scale,
            translation,
        )[0]
        if isinstance(point, np.ndarray):
            point.reshape(-1)[0] = float(mapped[0])
            point.reshape(-1)[1] = float(mapped[1])
        else:
            contour_array[index] = [[float(mapped[0]), float(mapped[1])]]


def _resample_raw_contour_payload(contour_array, count: int) -> np.ndarray:
    """Convert a raw contour payload into a resampled Nx2 contour for smoothing."""
    points = []
    if contour_array is None:
        return np.empty((0, 2), dtype=np.float64)
    for point in contour_array:
        if point is None:
            continue
        arr = np.asarray(point, dtype=np.float64)
        if arr.size < 2:
            continue
        flat = arr.reshape(-1)
        points.append([float(flat[0]), float(flat[1])])
    if len(points) < 3:
        return np.empty((0, 2), dtype=np.float64)
    return _resample_closed_path(np.asarray(points, dtype=np.float64), count)


def _raw_contour_payload_points(contour_array) -> np.ndarray:
    """Convert a raw contour payload into an Nx2 contour without changing ordering."""
    points = []
    if contour_array is None:
        return np.empty((0, 2), dtype=np.float64)
    for point in contour_array:
        if point is None:
            continue
        arr = np.asarray(point, dtype=np.float64)
        if arr.size < 2:
            continue
        flat = arr.reshape(-1)
        points.append([float(flat[0]), float(flat[1])])
    if len(points) < 3:
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray(points, dtype=np.float64)


def _nearest_points(source_points: np.ndarray, target_points: np.ndarray) -> np.ndarray:
    """Return the nearest target point for each source point."""
    if len(source_points) == 0 or len(target_points) == 0:
        return np.empty((0, 2), dtype=np.float64)
    target_tree = _build_kdtree(target_points)
    if target_tree is None:
        return np.empty((0, 2), dtype=np.float64)
    _, indices = target_tree.query(np.asarray(source_points, dtype=np.float64), k=1)
    return target_points[np.asarray(indices, dtype=np.int64)]


def _bounded_reference_smooth(source_points: np.ndarray, reference_points: np.ndarray) -> np.ndarray:
    """
    Nudge a smooth reference contour toward the captured contour without inheriting its noise.

    The correction is mostly along the local contour normal, with only a very small tangential
    adjustment so the DXF shape remains the primary geometry.
    """
    if len(source_points) < 3 or len(reference_points) < 3:
        return source_points

    nearest = _nearest_points(source_points, reference_points)
    corrected = source_points.copy()
    max_normal_shift_px = 5.0
    max_tangent_shift_px = 1.0

    for index, point in enumerate(source_points):
        prev_point = source_points[(index - 1) % len(source_points)]
        next_point = source_points[(index + 1) % len(source_points)]
        tangent = next_point - prev_point
        tangent_norm = float(np.linalg.norm(tangent))
        if tangent_norm <= 1e-9:
            continue
        tangent /= tangent_norm
        normal = np.array([-tangent[1], tangent[0]], dtype=np.float64)

        delta = nearest[index] - point
        tangent_component = float(np.dot(delta, tangent))
        normal_component = float(np.dot(delta, normal))

        corrected[index] = (
            point
            + np.clip(normal_component, -max_normal_shift_px, max_normal_shift_px) * normal
            + 0.15 * np.clip(tangent_component, -max_tangent_shift_px, max_tangent_shift_px) * tangent
        )

    return corrected


def _laplacian_smooth_closed_path(points: np.ndarray, iterations: int = 2, alpha: float = 0.2) -> np.ndarray:
    """Apply light closed-path Laplacian smoothing without collapsing the contour."""
    smoothed = np.asarray(points, dtype=np.float64).copy()
    if len(smoothed) < 3:
        return smoothed

    alpha = float(np.clip(alpha, 0.0, 1.0))
    for _ in range(max(int(iterations), 0)):
        prev_points = np.roll(smoothed, 1, axis=0)
        next_points = np.roll(smoothed, -1, axis=0)
        neighbor_mean = 0.5 * (prev_points + next_points)
        smoothed = (1.0 - alpha) * smoothed + alpha * neighbor_mean
    return smoothed


def _replace_raw_contour_payload(contour_array, points: np.ndarray) -> None:
    """Rewrite a raw contour payload from an Nx2 point array."""
    contour_array[:] = [
        [[float(point[0]), float(point[1])]]
        for point in np.asarray(points, dtype=np.float64)
    ]


def _apply_reference_smoothed_main_contour(
    aligned: dict,
    target_points: np.ndarray,
    source_centroid: np.ndarray,
    theta: float,
    scale: float,
    translation: np.ndarray,
) -> None:
    """Use the aligned DXF as a prior to smooth the captured contour, then store that result."""
    contour_array = _main_contour_payload(aligned)
    source_contour = _resample_raw_contour_payload(contour_array, count=360)
    if len(source_contour) < 3:
        _transform_contour_in_place(contour_array, source_centroid, theta, scale, translation)
        return

    aligned_reference = _transform_points(
        source_contour,
        source_centroid,
        theta,
        scale,
        translation,
    )
    # Use the captured contour as the visible/output contour, but denoise it by
    # pulling it gently toward the aligned DXF reference and then smoothing it.
    corrected_capture = _bounded_reference_smooth(target_points, aligned_reference)
    smoothed_capture = _laplacian_smooth_closed_path(corrected_capture, iterations=2, alpha=0.18)
    _replace_raw_contour_payload(contour_array, smoothed_capture)


def _estimate_uniform_scale(
    source_centered: np.ndarray,
    target_centered: np.ndarray,
    max_scale_deviation: float | None = DEFAULT_MAX_SCALE_DEVIATION,
    reference_scale: float = 1.0,
) -> float:
    """Estimate a single uniform contour scale from centered source and target samples."""
    source_norm = float(np.sqrt(np.sum(source_centered * source_centered)))
    target_norm = float(np.sqrt(np.sum(target_centered * target_centered)))
    if source_norm <= 1e-9 or target_norm <= 1e-9:
        return 1.0
    return _clamp_scale(target_norm / source_norm, max_scale_deviation, reference_scale=reference_scale)


def _alignment_error(source_points: np.ndarray, target_points: np.ndarray) -> float:
    """Score alignment by average nearest-neighbor distance from source to target points."""
    if len(source_points) == 0 or len(target_points) == 0:
        return float("inf")
    target_tree = _build_kdtree(target_points)
    if target_tree is None:
        return float("inf")
    distances, _ = target_tree.query(np.asarray(source_points, dtype=np.float64), k=1)
    return float(np.mean(np.asarray(distances, dtype=np.float64)))


def _symmetric_alignment_error(
    source_points: np.ndarray,
    target_points: np.ndarray,
    *,
    target_tree: cKDTree | None = None,
    source_tree: cKDTree | None = None,
) -> float:
    """Symmetric nearest-neighbor contour distance."""
    if len(source_points) == 0 or len(target_points) == 0:
        return float("inf")
    target_tree = target_tree or _build_kdtree(target_points)
    source_tree = source_tree or _build_kdtree(source_points)
    if target_tree is None or source_tree is None:
        return float("inf")
    forward = float(np.mean(np.asarray(target_tree.query(np.asarray(source_points, dtype=np.float64), k=1)[0], dtype=np.float64)))
    backward = float(np.mean(np.asarray(source_tree.query(np.asarray(target_points, dtype=np.float64), k=1)[0], dtype=np.float64)))
    return 0.5 * (forward + backward)


def _build_kdtree(points: np.ndarray) -> cKDTree | None:
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or len(points) == 0 or points.shape[1] < 2:
        return None
    return cKDTree(points[:, :2])


def _estimate_similarity_transform_indexed(
    source_points: np.ndarray,
    target_points: np.ndarray,
    source_center: np.ndarray,
    max_scale_deviation: float | None = DEFAULT_MAX_SCALE_DEVIATION,
    reference_scale: float = 1.0,
) -> tuple[float, float, np.ndarray]:
    """
    Estimate a similarity pose under indexed point correspondences.

    Returns parameters in the same convention used by _transform_points:
    rotate+scale around source_center, then apply translation.
    """
    if len(source_points) != len(target_points):
        raise ValueError("source_points and target_points must have equal length")

    src0 = source_points - source_center
    tgt_mean = np.mean(target_points, axis=0)
    tgt0 = target_points - tgt_mean

    H = src0.T @ tgt0
    U, S, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T

    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1.0
        R = Vt.T @ U.T

    src_var = float(np.sum(src0 * src0))
    if src_var <= 1e-12:
        scale = 1.0
    else:
        scale = float(np.sum(S) / src_var)
    scale = _clamp_scale(scale, max_scale_deviation, reference_scale=reference_scale)

    theta = float(np.arctan2(R[1, 0], R[0, 0]))

    rotated_scaled = _rotate_and_scale_points(source_points, source_center, theta, scale)
    translation = tgt_mean - np.mean(rotated_scaled, axis=0)
    return theta, scale, translation


def _wrap_angle(theta: float) -> float:
    """Normalize radians into [-pi, pi] to keep local search numerically stable."""
    wrapped = (float(theta) + np.pi) % (2.0 * np.pi) - np.pi
    return float(wrapped)


def _best_initial_pose(
    source_points: np.ndarray,
    target_points: np.ndarray,
    num_shifts: int = 36,
    max_scale_deviation: float | None = DEFAULT_MAX_SCALE_DEVIATION,
    reference_scale_override: float | None = None,
) -> tuple[float, float, np.ndarray]:
    """
    Search cyclic correspondences and both contour windings for a strong initial pose.
    Falls back to PCA-based initialization if needed.
    """
    if len(source_points) < 3 or len(target_points) < 3:
        return 0.0, 1.0, np.zeros(2, dtype=np.float64)

    if len(source_points) != len(target_points):
        count = min(len(source_points), len(target_points))
        source_points = _resample_closed_path(source_points, count)
        target_points = _resample_closed_path(target_points, count)

    source_center = np.mean(source_points, axis=0)
    reference_scale = (
        float(reference_scale_override)
        if reference_scale_override is not None
        else _robust_reference_scale(source_points, target_points)
    )
    n = len(source_points)
    shifts = np.unique(np.linspace(0, n - 1, num=min(max(int(num_shifts), 1), n), dtype=int))
    target_tree = _build_kdtree(target_points)

    best_error = float("inf")
    best_pose: tuple[float, float, np.ndarray] | None = None

    for reverse in (False, True):
        candidate_source = source_points[::-1].copy() if reverse else source_points
        for shift in shifts:
            rolled = np.roll(candidate_source, shift=int(shift), axis=0)
            theta, scale, translation = _estimate_similarity_transform_indexed(
                rolled,
                target_points,
                source_center,
                max_scale_deviation=max_scale_deviation,
                reference_scale=reference_scale,
            )
            transformed = _transform_points(rolled, source_center, theta, scale, translation)
            error = _symmetric_alignment_error(transformed, target_points, target_tree=target_tree)

            if error < best_error:
                best_error = error
                best_pose = (theta, scale, translation)

    # Coarse global angle sweep is intentionally limited. It helps on
    # ambiguous contours without turning every alignment into a brute-force job.
    target_centroid = np.mean(target_points, axis=0)
    source_centered = source_points - source_center
    target_centered = target_points - target_centroid
    base_scale = _estimate_uniform_scale(
        source_centered,
        target_centered,
        max_scale_deviation=max_scale_deviation,
        reference_scale=reference_scale,
    )
    for theta in np.deg2rad(np.arange(-180.0, 180.0, 15.0)):
        rotated = _rotate_and_scale_points(source_points, source_center, float(theta), base_scale)
        translation = target_centroid - np.mean(rotated, axis=0)
        transformed = rotated + translation
        error = _symmetric_alignment_error(transformed, target_points, target_tree=target_tree)
        if error < best_error:
            best_error = error
            best_pose = (float(theta), float(base_scale), np.asarray(translation, dtype=np.float64))

    if best_pose is not None:
        theta, scale, translation = best_pose
        return _wrap_angle(theta), scale, np.asarray(translation, dtype=np.float64)

    # Conservative fallback.
    source_centroid = np.mean(source_points, axis=0)
    source_centered = source_points - source_centroid

    base_theta = _principal_axis_angle(target_centered) - _principal_axis_angle(source_centered)
    base_scale = _estimate_uniform_scale(
        source_centered,
        target_centered,
        max_scale_deviation=max_scale_deviation,
        reference_scale=reference_scale,
    )

    candidate_thetas = [base_theta, base_theta + np.pi]
    best_theta = candidate_thetas[0]
    best_error = float("inf")
    for theta in candidate_thetas:
        translation = target_centroid - np.mean(
            _rotate_and_scale_points(source_points, source_centroid, theta, base_scale),
            axis=0,
        )
        transformed = _transform_points(source_points, source_centroid, theta, base_scale, translation)
        error = _symmetric_alignment_error(transformed, target_points, target_tree=target_tree)
        if error < best_error:
            best_error = error
            best_theta = theta

    best_translation = target_centroid - np.mean(
        _rotate_and_scale_points(source_points, source_centroid, best_theta, base_scale),
        axis=0,
    )
    return _wrap_angle(best_theta), base_scale, best_translation


def _select_trimmed_matches(
    transformed_source: np.ndarray,
    target_points: np.ndarray,
    indices: np.ndarray,
    trim_ratio: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Keep only the closest source-target pairs to reduce ICP sensitivity to outliers."""
    matched_targets = target_points[indices]
    distances = np.linalg.norm(transformed_source - matched_targets, axis=1)
    if len(distances) == 0:
        return np.empty((0,), dtype=int), matched_targets

    keep_count = max(3, min(len(distances), int(np.ceil(len(distances) * float(trim_ratio)))))
    keep_indices = np.argsort(distances)[:keep_count]
    return keep_indices, matched_targets[keep_indices]


def _nearest_neighbor_indices(
    source_points: np.ndarray,
    target_points: np.ndarray | None = None,
    *,
    target_tree: cKDTree | None = None,
) -> np.ndarray:
    """Return, for each source point, the index of the closest target point."""
    if target_tree is None:
        if target_points is None:
            return np.empty((0,), dtype=np.int64)
        target_tree = _build_kdtree(target_points)
    if target_tree is None or len(source_points) == 0:
        return np.empty((0,), dtype=np.int64)
    _, indices = target_tree.query(np.asarray(source_points, dtype=np.float64), k=1)
    return np.asarray(indices, dtype=np.int64)


def _refine_pose_icp(
    source_points: np.ndarray,
    target_points: np.ndarray,
    source_centroid: np.ndarray,
    theta: float,
    scale: float,
    translation: np.ndarray,
    iterations: int = 8,
    trim_ratio: float = 0.8,
    max_scale_deviation: float | None = DEFAULT_MAX_SCALE_DEVIATION,
    reference_scale_override: float | None = None,
) -> tuple[float, float, np.ndarray]:
    """
    Refine pose using a few ICP-like iterations:
    transform source, find nearest target matches, solve indexed similarity.
    """
    best_theta = float(theta)
    reference_scale = (
        float(reference_scale_override)
        if reference_scale_override is not None
        else _robust_reference_scale(source_points, target_points)
    )
    best_scale = _clamp_scale(scale, max_scale_deviation, reference_scale=reference_scale)
    best_translation = np.asarray(translation, dtype=np.float64)
    target_tree = _build_kdtree(target_points)

    previous_error = float("inf")

    for _ in range(max(int(iterations), 0)):
        transformed = _transform_points(
            source_points,
            source_centroid,
            best_theta,
            best_scale,
            best_translation,
        )
        indices = _nearest_neighbor_indices(transformed, target_tree=target_tree)
        keep_indices, matched_targets = _select_trimmed_matches(
            transformed,
            target_points,
            indices,
            trim_ratio=trim_ratio,
        )
        if len(keep_indices) < 3:
            break

        candidate_theta, candidate_scale, candidate_translation = _estimate_similarity_transform_indexed(
            source_points[keep_indices],
            matched_targets,
            source_centroid,
            max_scale_deviation=max_scale_deviation,
            reference_scale=reference_scale,
        )
        candidate_transformed = _transform_points(
            source_points,
            source_centroid,
            candidate_theta,
            candidate_scale,
            candidate_translation,
        )
        candidate_error = _symmetric_alignment_error(candidate_transformed, target_points, target_tree=target_tree)

        if candidate_error + 1e-9 < previous_error:
            best_theta = _wrap_angle(candidate_theta)
            best_scale = _clamp_scale(candidate_scale, max_scale_deviation, reference_scale=reference_scale)
            best_translation = np.asarray(candidate_translation, dtype=np.float64)
            previous_error = candidate_error
        else:
            break

    return best_theta, best_scale, best_translation


def _pose_score_from_scorer(
    scorer: _PoseScorer,
    theta: float,
    scale: float,
    translation: np.ndarray,
) -> float:
    """
    Combined alignment score.

    Higher is better:
    - rewards mask overlap
    - penalizes symmetric contour distance
    """
    return scorer.score(theta, scale, translation)


def _refine_alignment_with_mask_overlap(
    source_points: np.ndarray,
    target_points: np.ndarray,
    source_centroid: np.ndarray,
    initial_theta: float,
    initial_scale: float,
    initial_translation: np.ndarray,
    overlap_fn,
    max_scale_deviation: float | None = DEFAULT_MAX_SCALE_DEVIATION,
    reference_scale_override: float | None = None,
) -> tuple[float, float, np.ndarray]:
    """Refine rotation, scale, and translation by searching for the best local pose score."""
    best_theta = float(initial_theta)
    reference_scale = (
        float(reference_scale_override)
        if reference_scale_override is not None
        else _robust_reference_scale(source_points, target_points)
    )
    best_scale = _clamp_scale(initial_scale, max_scale_deviation, reference_scale=reference_scale)
    best_translation = np.asarray(initial_translation, dtype=np.float64)
    scorer = _PoseScorer(source_points, target_points, source_centroid, overlap_fn)
    best_score = _pose_score_from_scorer(scorer, best_theta, best_scale, best_translation)

    rotation_steps_deg = [4.0, 0.5, 0.05]
    translation_steps_px = [8.0, 0.75, 0.1]
    scale_steps = [0.025, 0.005, 0.001]

    for rotation_step_deg, translation_step_px, scale_step in zip(
        rotation_steps_deg,
        translation_steps_px,
        scale_steps,
    ):
        improved = True
        dtheta = np.deg2rad(rotation_step_deg)

        while improved:
            improved = False
            best_candidate = None
            best_candidate_score = best_score

            translation_offsets = [
                np.array([dx, dy], dtype=np.float64)
                for dx in (-translation_step_px, 0.0, translation_step_px)
                for dy in (-translation_step_px, 0.0, translation_step_px)
                if not (dx == 0.0 and dy == 0.0)
            ]

            candidates: list[tuple[float, float, np.ndarray]] = []

            # Pure rotation candidates. The final stage is intentionally small
            # enough to nudge the contour into sub-pixel agreement.
            candidates.extend(
                [
                    (_wrap_angle(best_theta - dtheta), best_scale, best_translation),
                    (_wrap_angle(best_theta + dtheta), best_scale, best_translation),
                ]
            )

            # Pure scale candidates
            candidates.extend(
                [
                    (best_theta, _clamp_scale(best_scale * (1.0 - scale_step), max_scale_deviation, reference_scale=reference_scale), best_translation),
                    (best_theta, _clamp_scale(best_scale * (1.0 + scale_step), max_scale_deviation, reference_scale=reference_scale), best_translation),
                ]
            )

            # Pure translation candidates
            candidates.extend(
                [
                    (best_theta, best_scale, best_translation + offset)
                    for offset in translation_offsets
                ]
            )

            # Coupled rotate + translate candidates
            for theta_candidate in (_wrap_angle(best_theta - dtheta), _wrap_angle(best_theta + dtheta)):
                for offset in translation_offsets:
                    candidates.append((theta_candidate, best_scale, best_translation + offset))

            # Coupled scale + translate candidates
            for scale_candidate in (
                _clamp_scale(best_scale * (1.0 - scale_step), max_scale_deviation, reference_scale=reference_scale),
                _clamp_scale(best_scale * (1.0 + scale_step), max_scale_deviation, reference_scale=reference_scale),
            ):
                for offset in translation_offsets:
                    candidates.append((best_theta, scale_candidate, best_translation + offset))

            for candidate_theta, candidate_scale, candidate_translation in candidates:
                candidate_translation = np.asarray(candidate_translation, dtype=np.float64)
                candidate_theta = _wrap_angle(candidate_theta)
                candidate_score = _pose_score_from_scorer(
                    scorer,
                    candidate_theta,
                    float(candidate_scale),
                    candidate_translation,
                )
                if candidate_score > best_candidate_score + 1e-12:
                    best_candidate_score = candidate_score
                    best_candidate = (
                        candidate_theta,
                        candidate_scale,
                        candidate_translation,
                    )

            if best_candidate is not None:
                best_theta, best_scale, best_translation = best_candidate
                best_score = best_candidate_score
                improved = True

    return best_theta, best_scale, best_translation


def _mask_overlap_for_pose(
    source_points: np.ndarray,
    target_points: np.ndarray,
    source_centroid: np.ndarray,
    theta: float,
    scale: float,
    translation: np.ndarray,
    overlap_fn,
) -> float:
    """Evaluate the contour mask overlap score for one candidate alignment pose."""
    transformed = _transform_points(
        source_points,
        source_centroid,
        theta,
        scale,
        translation,
    )
    return float(overlap_fn(transformed, target_points))

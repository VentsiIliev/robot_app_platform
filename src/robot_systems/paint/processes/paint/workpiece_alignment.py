from __future__ import annotations
import copy
import numpy as np

def align_raw_workpiece_to_contour(raw: dict, captured_contour) -> dict:
    """Align a saved raw workpiece contour set onto a newly captured contour in image space."""
    from src.engine.vision.implementation.VisionSystem.features.contour_matching.utils import calculate_mask_overlap

    aligned = copy.deepcopy(raw)
    source_points = _extract_raw_contour_points(aligned)
    target_points = _normalize_contour_points(captured_contour)
    if len(source_points) < 3 or len(target_points) < 3:
        return aligned

    source_resampled = _resample_closed_path(source_points, 180)
    target_resampled = _resample_closed_path(target_points, 180)
    source_centroid = np.mean(source_resampled, axis=0)
    target_centroid = np.mean(target_resampled, axis=0)
    source_centered = source_resampled - source_centroid
    target_centered = target_resampled - target_centroid

    # Build a first-pass pose from global contour statistics so the local
    # overlap search starts close enough to converge quickly.
    base_theta = _principal_axis_angle(target_centered) - _principal_axis_angle(source_centered)
    base_scale = _estimate_uniform_scale(source_centered, target_centered)

    # PCA gives an axis, not a directed heading, so a 180-degree flip is
    # equally plausible. Try both and keep the lower point-set error.
    candidate_thetas = [base_theta, base_theta + np.pi]
    best_theta = min(
        candidate_thetas,
        key=lambda theta: _alignment_error(
            _transform_points(source_resampled, source_centroid, theta, base_scale, target_centroid),
            target_resampled,
        ),
    )

    # Translation is solved after rotation+scale so the transformed source
    # centroid lands on the target centroid before refinement begins.
    initial_translation = target_centroid - _rotate_and_scale_points(
        source_resampled,
        source_centroid,
        best_theta,
        base_scale,
    ).mean(axis=0)
    best_theta, best_scale, best_translation = _refine_alignment_with_mask_overlap(
        source_resampled,
        target_resampled,
        source_centroid,
        best_theta,
        base_scale,
        initial_translation,
        calculate_mask_overlap,
    )

    def _transform_contour(contour_array):
        for point in contour_array or []:
            if point and point[0]:
                vec = np.array([float(point[0][0]), float(point[0][1])], dtype=float)
                mapped = _transform_points(
                    vec[None, :],
                    source_centroid,
                    best_theta,
                    best_scale,
                    best_translation,
                )[0]
                point[0][0] = float(mapped[0])
                point[0][1] = float(mapped[1])

    _transform_contour(aligned.get("contour"))
    spray = aligned.get("sprayPattern") or {}
    for key in ("Contour", "Fill"):
        for segment in spray.get(key, []):
            _transform_contour(segment.get("contour"))
    return aligned


def _extract_raw_contour_points(raw: dict) -> np.ndarray:
    """Extract the main raw workpiece contour as an Nx2 numpy array."""
    contour = raw.get("contour") or []
    points = [point[0] for point in contour if point and point[0]]
    if not points:
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray([[float(point[0]), float(point[1])] for point in points], dtype=np.float64)


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


def _rotate_and_scale_points(points: np.ndarray, center: np.ndarray, theta: float, scale: float) -> np.ndarray:
    """Rotate and uniformly scale points around a contour center."""
    rotation = np.array(
        [
            [np.cos(theta), -np.sin(theta)],
            [np.sin(theta), np.cos(theta)],
        ],
        dtype=np.float64,
    )
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


def _estimate_uniform_scale(source_centered: np.ndarray, target_centered: np.ndarray) -> float:
    """Estimate a single uniform contour scale from centered source and target samples."""
    source_norm = float(np.sqrt(np.sum(source_centered * source_centered)))
    target_norm = float(np.sqrt(np.sum(target_centered * target_centered)))
    if source_norm <= 1e-9 or target_norm <= 1e-9:
        return 1.0
    return max(1e-3, target_norm / source_norm)


def _alignment_error(source_points: np.ndarray, target_points: np.ndarray) -> float:
    """Score alignment by average nearest-neighbor distance from source to target points."""
    if len(source_points) == 0 or len(target_points) == 0:
        return float("inf")
    deltas = source_points[:, None, :] - target_points[None, :, :]
    distances = np.linalg.norm(deltas, axis=2)
    return float(np.mean(np.min(distances, axis=1)))


def _refine_alignment_with_mask_overlap(
    source_points: np.ndarray,
    target_points: np.ndarray,
    source_centroid: np.ndarray,
    initial_theta: float,
    initial_scale: float,
    initial_translation: np.ndarray,
    overlap_fn,
) -> tuple[float, float, np.ndarray]:
    """Refine rotation, scale, and translation by searching for best contour mask overlap."""
    best_theta = float(initial_theta)
    best_scale = max(1e-3, float(initial_scale))
    best_translation = np.asarray(initial_translation, dtype=np.float64)
    best_overlap = _mask_overlap_for_pose(
        source_points,
        target_points,
        source_centroid,
        best_theta,
        best_scale,
        best_translation,
        overlap_fn,
    )

    rotation_steps_deg = [6.0, 2.0, 0.5]
    translation_steps_px = [12.0, 4.0, 1.5]
    scale_steps = [0.10, 0.03, 0.01]

    for rotation_step_deg, translation_step_px, scale_step in zip(rotation_steps_deg, translation_steps_px, scale_steps):
        # Coarse-to-fine hill climb: at each resolution, keep walking as long
        # as any neighboring candidate improves the mask-overlap score.
        improved = True
        while improved:
            improved = False
            candidates: list[tuple[float, float, np.ndarray]] = [
                (best_theta - np.deg2rad(rotation_step_deg), best_scale, best_translation),
                (best_theta + np.deg2rad(rotation_step_deg), best_scale, best_translation),
                (best_theta, max(1e-3, best_scale * (1.0 - scale_step)), best_translation),
                (best_theta, best_scale * (1.0 + scale_step), best_translation),
                (best_theta, best_scale, best_translation + np.array([translation_step_px, 0.0], dtype=np.float64)),
                (best_theta, best_scale, best_translation + np.array([-translation_step_px, 0.0], dtype=np.float64)),
                (best_theta, best_scale, best_translation + np.array([0.0, translation_step_px], dtype=np.float64)),
                (best_theta, best_scale, best_translation + np.array([0.0, -translation_step_px], dtype=np.float64)),
                (best_theta, best_scale, best_translation + np.array([translation_step_px, translation_step_px], dtype=np.float64)),
                (best_theta, best_scale, best_translation + np.array([translation_step_px, -translation_step_px], dtype=np.float64)),
                (best_theta, best_scale, best_translation + np.array([-translation_step_px, translation_step_px], dtype=np.float64)),
                (best_theta, best_scale, best_translation + np.array([-translation_step_px, -translation_step_px], dtype=np.float64)),
            ]
            for candidate_theta, candidate_scale, candidate_translation in candidates:
                # Overlap is the optimization target because it is more stable
                # than nearest-neighbor distance once contours already roughly align.
                overlap = _mask_overlap_for_pose(
                    source_points,
                    target_points,
                    source_centroid,
                    float(candidate_theta),
                    float(candidate_scale),
                    np.asarray(candidate_translation, dtype=np.float64),
                    overlap_fn,
                )
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_theta = float(candidate_theta)
                    best_scale = float(candidate_scale)
                    best_translation = np.asarray(candidate_translation, dtype=np.float64)
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

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional
import logging

import cv2
import numpy as np

from src.engine.robot.path_preparation.debug import _save_contour_canonicalization_steps_debug_plot, \
    _save_contour_reordering_debug_plot

_logger = logging.getLogger(__name__)

from src.engine.geometry.planar import nearest_axis_equivalent_degrees, unwrap_degrees
from src.engine.robot.path_preparation.geometry import (
    PATH_TANGENT_HEADING_DEADBAND_DEG,
    PATH_TANGENT_LOOKAHEAD_DISTANCE_MM,
    canonicalize_closed_contour_points,
    compute_pickup_rz_from_robot_contour,
    compute_pickup_rz_from_robot_path,
    compute_pickup_rz_from_robot_contour_with_direction,
    has_valid_contour,
    rebuild_pose_path_from_xy,
)
from src.engine.robot.path_preparation.i_workpiece_path_preparation_service import IWorkpiecePathPreparationService
from src.engine.robot.path_preparation import config
from src.engine.robot.path_preparation.pixel_to_mm import (
    GeometryPpmAnchorStrategy,
    GeometryScaleCache,
    HomographyOnlyPreviewStrategy,
    HomographyResidualStrategy,
    PixelToMmContext,
)



@dataclass(frozen=True)
class WorkpieceExecutionPlan:
    """Complete execution plan for a workpiece, holding all path representations and per-segment job specs.

    Stores the transformation chain: raw pixel paths → prepared/curve/sampled poses → final
    execution splines, plus per-job metadata (velocity, acceleration, pickup point, target offsets).
    """
    workpiece: dict
    raw_paths: list[list[list[float]]]
    prepared_paths: list[list[list[float]]]
    curve_paths: list[list[list[float]]]
    sampled_paths: list[list[list[float]]]
    execution_jobs: list[dict]
    total_spline_pts: int
    raw_pixel_paths: list[list[list[float]]] = field(default_factory=list)
    raw_homography_paths: list[list[list[float]]] = field(default_factory=list)

    def execution_paths(self) -> list[list[list[float]]]:
        """Extract the final execution path from each job, falling back to the legacy path key."""
        return [
            [list(point) for point in (job.get("execution_path") or job.get("path") or [])]
            for job in self.execution_jobs
        ]


def _safe_float(value, default: float) -> float:
    """Convert *value* to float, returning *default* on None/empty/conversion failure."""
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _resample_execution_path(
        path: list[list[float]],
        target_spacing_mm: float,
        *,
        preserve_waypoint_xy: np.ndarray | None = None,
) -> list[list[float]]:
    """Resample a pose path while forcing selected XY anchors to remain in the output."""
    if len(path) < 2:
        return [list(point) for point in path]

    target_spacing_mm = max(1.0, float(target_spacing_mm))
    points = np.asarray(path, dtype=float)
    if points.ndim != 2 or points.shape[0] < 2:
        return [list(point) for point in path]
    segment_lengths_all = np.linalg.norm(np.diff(points[:, :3], axis=0), axis=1)
    cumulative_all = np.concatenate([[0.0], np.cumsum(segment_lengths_all)])
    total_distance = float(cumulative_all[-1])
    if total_distance <= 1e-9:
        return [list(path[0])]

    preserve_distances: list[float] = []
    if preserve_waypoint_xy is not None and points.shape[1] >= 2:
        try:
            preserve_xy = np.asarray(preserve_waypoint_xy, dtype=float).reshape(-1, 2)
        except (TypeError, ValueError):
            preserve_xy = np.empty((0, 2), dtype=float)
        if len(preserve_xy):
            for index, point in enumerate(points):
                if bool(np.any(np.linalg.norm(preserve_xy - point[:2], axis=1) <= 1e-6)):
                    preserve_distances.append(float(cumulative_all[index]))

    sample_distances = list(np.arange(0.0, total_distance, target_spacing_mm))
    sample_distances.extend(preserve_distances)
    sample_distances.append(total_distance)
    sample_distances = sorted(set(round(float(distance), 9) for distance in sample_distances))

    resampled_array = np.column_stack(
        [np.interp(sample_distances, cumulative_all, points[:, dim]) for dim in range(points.shape[1])]
    )
    resampled: list[list[float]] = []
    for point in resampled_array.tolist():
        if not resampled or any(abs(float(a) - float(b)) > 1e-9 for a, b in zip(resampled[-1], point)):
            resampled.append(point)
    return resampled


def _densify_xy_preserving_anchors(xy_points: np.ndarray, target_spacing_mm: float) -> np.ndarray:
    """Densify a 2D point path to at most *target_spacing_mm* intervals, keeping all original vertices.

    Uses linear interpolation along the cumulative arclength so that original vertices
    (anchors) appear verbatim in the output. The output is strictly XY-only (no Z/RX/RY).
    """
    points = np.asarray(xy_points, dtype=float)
    if points.ndim != 2 or points.shape[0] < 2 or points.shape[1] < 2:
        return points[:, :2].copy() if points.ndim == 2 and points.shape[1] >= 2 else np.empty((0, 2), dtype=float)

    points = points[:, :2].copy()
    segment_lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
    keep_mask = np.concatenate([[True], segment_lengths > 1e-9])
    points = points[keep_mask]
    if len(points) < 2:
        return points

    segment_lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    total_length = float(cumulative[-1])
    if total_length <= 1e-9:
        return points

    target_spacing_mm = max(0.1, float(target_spacing_mm))
    sample_distances = list(np.arange(0.0, total_length, target_spacing_mm))
    sample_distances.extend(float(distance) for distance in cumulative)
    sample_distances.append(total_length)
    sample_distances = sorted(set(round(float(distance), 9) for distance in sample_distances))

    dense = np.column_stack(
        [np.interp(sample_distances, cumulative, points[:, dim]) for dim in range(2)]
    )
    return dense


def _merge_unique_xy_points(*point_sets: np.ndarray | None) -> np.ndarray:
    """Union of multiple 2-D point sets, deduplicated within a 1e-6 distance tolerance."""
    merged: list[np.ndarray] = []
    for point_set in point_sets:
        if point_set is None:
            continue
        try:
            points = np.asarray(point_set, dtype=float).reshape(-1, 2)
        except (TypeError, ValueError):
            continue
        for point in points:
            if not merged or not any(float(np.linalg.norm(point - existing)) <= 1e-6 for existing in merged):
                merged.append(point.copy())
    if not merged:
        return np.empty((0, 2), dtype=float)
    return np.asarray(merged, dtype=float)


def _signed_turn_degrees(prev: np.ndarray, current: np.ndarray, nxt: np.ndarray) -> float:
    """Signed turning angle (degrees) at *current* when travelling *prev → current → nxt*.

    Positive = counter-clockwise turn. Returns 0 if either segment is a zero-length
    degenerate edge.
    """
    incoming = np.asarray(current, dtype=float) - np.asarray(prev, dtype=float)
    outgoing = np.asarray(nxt, dtype=float) - np.asarray(current, dtype=float)
    in_len = float(np.linalg.norm(incoming))
    out_len = float(np.linalg.norm(outgoing))
    if in_len <= 1e-9 or out_len <= 1e-9:
        return 0.0
    cross = float(incoming[0] * outgoing[1] - incoming[1] * outgoing[0])
    dot = float(np.dot(incoming, outgoing))
    return float(np.degrees(np.arctan2(cross, dot)))




def _sharp_tangent_boundary_xy(anchor_xy: np.ndarray, threshold_deg: float = config._SHARP_TANGENT_BOUNDARY_DEG) -> np.ndarray:
    """Find XY points where the path makes a sharp turn (≥*threshold_deg* cumulative or peak).

    Clusters consecutive high-turn vertices and returns one representative point per
    compact cluster (≤3 vertices) or clusters whose peak turn exceeds the threshold.
    Rounded arcs (long clusters with distributed turn) are excluded.
    """
    points = np.asarray(anchor_xy, dtype=float)
    if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] < 2:
        return np.empty((0, 2), dtype=float)
    points = points[:, :2].copy()
    closed = len(points) >= 4 and float(np.linalg.norm(points[0] - points[-1])) <= 1e-6
    if closed:
        points = points[:-1]
    if len(points) < 3:
        return np.empty((0, 2), dtype=float)

    turns = np.zeros(len(points), dtype=float)
    turn_range = range(len(points)) if closed else range(1, len(points) - 1)
    for index in turn_range:
        turns[index] = _signed_turn_degrees(
            points[index - 1],
            points[index],
            points[(index + 1) % len(points)],
        )
    abs_turns = np.abs(turns)
    threshold = max(float(threshold_deg), 1.0)
    active_threshold = max(5.0, threshold * 0.2)
    candidate_indices = [index for index in turn_range if abs_turns[index] >= active_threshold]
    if not candidate_indices:
        return np.empty((0, 2), dtype=float)

    clusters: list[list[int]] = []
    current_cluster: list[int] = []
    for index in candidate_indices:
        if current_cluster and index != current_cluster[-1] + 1:
            clusters.append(current_cluster)
            current_cluster = []
        current_cluster.append(index)
    if current_cluster:
        clusters.append(current_cluster)

    if closed and len(clusters) > 1 and clusters[0][0] == 0 and clusters[-1][-1] == len(points) - 1:
        clusters[0] = clusters[-1] + clusters[0]
        clusters.pop()

    sharp_indices: list[int] = []
    for cluster in clusters:
        total_turn = float(np.sum(abs_turns[cluster]))
        peak_turn = float(np.max(abs_turns[cluster]))
        if total_turn < threshold and peak_turn < threshold:
            continue
        # Rounded arcs normally distribute turn over many anchors. A hard
        # corner may be one vertex or a short bevel after cleanup, so mark the
        # start of compact turn clusters and let longer clusters flow as arcs.
        if len(cluster) <= 3 or peak_turn >= threshold:
            sharp_indices.append(cluster[0] % len(points))
    if not sharp_indices:
        return np.empty((0, 2), dtype=float)
    return points[sorted(set(sharp_indices))]


def _resolve_segment_interpolation_settings(settings: dict) -> tuple[float, float, float, float]:
    """Extract and clamp the four interpolation parameters from per-segment *settings*.

    Returns (preprocess_min_spacing, interpolation_spacing, dense_sampling_factor, execution_spacing),
    each floored at a safe minimum to prevent degenerate values.
    """
    preprocess_spacing_mm = max(
        0.1,
        _safe_float(settings.get(config._SEGMENT_PREPROCESS_MIN_SPACING_KEY), config._EXECUTION_MIN_PREPROCESS_SPACING_MM),
    )
    interpolation_spacing_mm = max(
        0.5,
        _safe_float(settings.get(config._SEGMENT_INTERPOLATION_SPACING_KEY), config._EXECUTION_INTERPOLATION_SPACING_MM),
    )
    dense_sampling_factor = max(
        0.05,
        _safe_float(settings.get(config._SEGMENT_DENSE_SAMPLING_FACTOR_KEY), config._EXECUTION_DENSE_SAMPLING_FACTOR),
    )
    execution_spacing_mm = max(
        1.0,
        _safe_float(settings.get(config._SEGMENT_EXECUTION_SPACING_KEY), config._EXECUTION_DEFAULT_OUTPUT_SPACING_MM),
    )
    return preprocess_spacing_mm, interpolation_spacing_mm, dense_sampling_factor, execution_spacing_mm


def _resolve_segment_tangent_settings(settings: dict) -> tuple[float, float]:
    """Extract the tangent heading lookahead distance and deadband from per-segment *settings*.

    Each segment can override the global defaults (PATH_TANGENT_LOOKAHEAD_DISTANCE_MM,
    PATH_TANGENT_HEADING_DEADBAND_DEG) via its own settings dict.
    """
    lookahead_distance_mm = max(
        1.0,
        _safe_float(settings.get(config._SEGMENT_TANGENT_LOOKAHEAD_DISTANCE_KEY), PATH_TANGENT_LOOKAHEAD_DISTANCE_MM),
    )
    heading_deadband_deg = max(
        0.0,
        _safe_float(settings.get(config._SEGMENT_TANGENT_DEADBAND_KEY), PATH_TANGENT_HEADING_DEADBAND_DEG),
    )
    return lookahead_distance_mm, heading_deadband_deg


def _auto_input_densify_spacing(path_pts: list[list[float]], interpolation_spacing_mm: float) -> float:
    """Return a spacing hint for pre-densification if any segment exceeds the trigger ratio.

    When the longest segment in *path_pts* is > *interpolation_spacing_mm* × TRIGGER_RATIO
    (2.5×), densify at TARGET_RATIO (1.25×) so the interpolation pipeline sees evenly-
    spaced inputs. Returns 0.0 (no densification needed) when all segments are already fine.
    """
    if len(path_pts) < 3:
        return 0.0

    xy = np.asarray(path_pts, dtype=float)[:, :2]
    diffs = np.diff(xy, axis=0)

    seg_lengths = np.linalg.norm(diffs, axis=1)
    seg_lengths = seg_lengths[seg_lengths > 1e-9]

    if seg_lengths.size == 0:
        return 0.0
    max_segment = float(np.max(seg_lengths))
    trigger_spacing = max(float(interpolation_spacing_mm) * config._AUTO_DENSIFY_TRIGGER_RATIO, 1.0)

    if max_segment <= trigger_spacing:
        return 0.0

    return max(1.0, float(interpolation_spacing_mm) * config._AUTO_DENSIFY_TARGET_RATIO)


def _is_closed_contour(path_pts: list[list[float]]) -> bool:
    """True if the first and last XY point of *path_pts* coincide within 1e-6 mm."""
    if len(path_pts) < 3:
        return False

    try:
        start = np.asarray(path_pts[0][:2], dtype=float)
        end = np.asarray(path_pts[-1][:2], dtype=float)
    except Exception:
        return False

    return float(np.linalg.norm(start - end)) <= 1e-6


class DefaultWorkpiecePathPreparationService(IWorkpiecePathPreparationService):
    def __init__(
            self,
            *,
            logger,
            segment_config,
            transformer=None,
            resolver=None,
            transformer_getter: Optional[Callable[[], object]] = None,
            resolver_getter: Optional[Callable[[], object]] = None,
            z_min: float = 0.0,
            rz_mode: str = "constant",
            execute_from_workpiece_layer: bool = False,
            target_point_name: str = "",
            pickup_target_point_name: str = "",
            calibration_frame_name: str = "",
            pixel_height_compensation_fn: Optional[Callable[[float], tuple[float, float]]] = None,
            base_position_provider: Optional[Callable[[], Optional[list[float]]]] = None,
            pickup_axis_alignment_sign: float = 1.0,
            pixel_to_mm_mode: str = config.PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR,
            debug_plot_dir: Optional[str] = None,
    ) -> None:
        """Configure the service with transformer/resolver references and per-application settings.

        Calibration objects can be injected directly (*transformer*, *resolver*) or resolved
        lazily via callables (*transformer_getter*, *resolver_getter*). The *rz_mode* controls
        whether heading is constant (segment-level rz_angle) or computed per-point from the path
        tangent. When *execute_from_workpiece_layer* is True the workpiece contour is used
        instead of sprayPattern data.
        """
        self._logger = logger
        self._segment_config = segment_config
        self._transformer = transformer
        self._resolver = resolver
        self._transformer_getter = transformer_getter
        self._resolver_getter = resolver_getter
        self._z_min = float(z_min)
        self._rz_mode = str(rz_mode or "constant").strip().lower()
        self._execute_from_workpiece_layer = bool(execute_from_workpiece_layer)
        self._target_point_name = str(target_point_name or "").strip().lower()
        self._pickup_target_point_name = str(pickup_target_point_name or self._target_point_name or "").strip().lower()
        self._calibration_frame_name = str(calibration_frame_name or "").strip().lower()
        self._pixel_height_compensation_fn = pixel_height_compensation_fn
        self._base_position_provider = base_position_provider
        self._debug_plot_dir = str(debug_plot_dir) if debug_plot_dir else ""
        self._geometry_scale_cache = GeometryScaleCache()
        self._geometry_ppm_strategy = GeometryPpmAnchorStrategy()
        self._homography_residual_strategy = HomographyResidualStrategy()
        self._homography_preview_strategy = HomographyOnlyPreviewStrategy()
        try:
            pickup_alignment_sign = float(pickup_axis_alignment_sign)
        except (TypeError, ValueError):
            pickup_alignment_sign = 1.0
        self._pickup_axis_alignment_sign = 1.0 if pickup_alignment_sign >= 0.0 else -1.0
        resolved_mode = str(pixel_to_mm_mode or config.PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR).strip().lower()
        if resolved_mode not in config._PIXEL_TO_MM_MODES:
            raise ValueError(
                f"Unsupported pixel_to_mm_mode {pixel_to_mm_mode!r}; "
                f"expected one of {sorted(config._PIXEL_TO_MM_MODES)}"
            )
        self._pixel_to_mm_mode = resolved_mode

    def _current_transformer(self):
        """Return the active pixel-to-robot transformer, resolving lazily if a getter is set."""
        if self._transformer_getter is not None:
            try:
                return self._transformer_getter()
            except Exception:
                self._logger.debug("Path preparation transformer lookup failed", exc_info=True)
        return self._transformer

    def _current_resolver(self):
        """Return the active calibration resolver, resolving lazily if a getter is set."""
        if self._resolver_getter is not None:
            try:
                return self._resolver_getter()
            except Exception:
                self._logger.debug("Path preparation resolver lookup failed", exc_info=True)
        return self._resolver

    def _resolve_target_point_metadata(self, target_point_name: str, frame_name: str) -> tuple[
        str, float, float, float]:
        """Look up the target-point offset and frame reference RZ from the calibration resolver.

        Returns (resolved_name, offset_x, offset_y, reference_rz). Returns zero defaults
        when the resolver or target point is unavailable.
        """
        resolved_name = str(target_point_name or "").strip().lower()
        offset_x = 0.0
        offset_y = 0.0
        reference_rz = 0.0
        resolver = self._current_resolver()
        if resolver is not None and resolved_name:
            try:
                point = resolver.registry.by_name(resolved_name)
                offset_x = float(getattr(point, "offset_x", 0.0))
                offset_y = float(getattr(point, "offset_y", 0.0))
            except Exception:
                offset_x = 0.0
                offset_y = 0.0
            try:
                frame_obj = resolver.get_frame(str(frame_name or "").strip().lower())
                mapper = getattr(frame_obj, "mapper", None) if frame_obj is not None else None
                target_pose = getattr(mapper, "target_pose", None) if mapper is not None else None
                reference_rz = float(getattr(target_pose, "rz", 0.0)) if target_pose is not None else 0.0
            except Exception:
                reference_rz = 0.0
        return resolved_name, offset_x, offset_y, reference_rz

    def build_execution_plan(self, workpiece: dict, skip_debug_plot: bool = False) -> WorkpieceExecutionPlan:
        """Main entry point: convert a workpiece dict into a fully-prepared execution plan.

        The pipeline is:
          1. Select source — workpiece layer contour or sprayPattern paths.
          2. Pixel→robot transform — via calibration resolver or fallback transformer.
          3. Interpolation — densify, smooth, and optionally detect sharp tangent boundaries.
          4. Heading reconstruction — constant RZ or path-tangent-aligned.
          5. Execution resampling — final evenly-spaced path with anchor-point preservation.
          6. Pickup resolution — compute the first-segment pickup XY and RZ.
        """
        from src.engine.robot.path_interpolation.new_interpolation.interpolation_pipeline import (
            ContourPathPipeline,
            InterpolationConfig,
            PreprocessConfig,
        )

        merged = workpiece
        original_pickup_source = dict(merged)
        if has_valid_contour(merged.get("contour")):
            try:
                original_pickup_source["contour"] = np.array(merged.get("contour", []), dtype=np.float32).copy()
            except Exception:
                original_pickup_source["contour"] = merged.get("contour")
        spray_pattern = merged.get("sprayPattern", {})
        workpiece_height_mm = _safe_float(merged.get("height_mm"), config._DEFAULT_WORKPIECE_HEIGHT_MM)
        default_pivot_offset_mm = _safe_float(merged.get("offset"), 0.0)
        execution_target_name, execution_target_offset_x, execution_target_offset_y, execution_reference_rz = (
            self._resolve_target_point_metadata(self._target_point_name, self._calibration_frame_name)
        )
        pickup_target_name, pickup_target_offset_x, pickup_target_offset_y, pickup_reference_rz = (
            self._resolve_target_point_metadata(self._pickup_target_point_name, self._calibration_frame_name)
        )
        use_workpiece_layer = False
        self._logger.debug(f"SPRAY PATTERN: {spray_pattern}")
        contour = spray_pattern.get("Contour") or None
        fill = spray_pattern.get("Fill") or None

        has_workpiece_contour = has_valid_contour(merged.get("contour"))
        if self._execute_from_workpiece_layer and has_workpiece_contour:
            use_workpiece_layer = True
            if contour or fill:
                self._logger.info(
                    "[EXECUTE] Using cleaned workpiece layer for execution; ignoring sprayPattern paths because execute_from_workpiece_layer=True"
                )
            else:
                self._logger.info("[EXECUTE] No spray patterns found; using workpiece layer for execution")
        elif not contour and not fill:
            self._logger.warning("No spray patterns found — draw Contour or Fill paths first")
            self._logger.warning("No workpiece contour found")
            # raise ValueError("No spray patterns found — draw Contour or Fill paths first")

        robot_paths = []
        pickup_px = self._extract_pickup_pixel(original_pickup_source)
        pickup_xy = None
        pickup_rz = 0.0
        pickup_camera_xy = None
        pickup_rz_source_path: list[list[float]] | None = None
        pickup_rz_source_contour: list[list[float]] | None = None

        if use_workpiece_layer:
            self._logger.debug(f"USING WORKPIECE LAYER")
            contour_arr = merged.get("contour", [])
            settings = {key: value for key, value in merged.items() if key not in {"contour", "sprayPattern"}}
            settings["height_mm"] = workpiece_height_mm
            if not isinstance(contour_arr, np.ndarray):
                contour_arr = np.array(contour_arr, dtype=np.float32)
            if contour_arr.size != 0:
                raw_pts_px = np.asarray(contour_arr.reshape(-1, 2), dtype=np.float64)
                if config._CANONICALIZE_WORKPIECE_LAYER_CONTOUR and len(raw_pts_px) >= 3:
                    _save_contour_canonicalization_steps_debug_plot(raw_pts_px, pickup_px)
                pts_px = (
                    canonicalize_closed_contour_points(raw_pts_px)
                    if config._CANONICALIZE_WORKPIECE_LAYER_CONTOUR
                    else raw_pts_px
                )
                if config._CANONICALIZE_WORKPIECE_LAYER_CONTOUR and len(raw_pts_px) >= 3 and len(pts_px) >= 3:
                    _save_contour_reordering_debug_plot(raw_pts_px, pts_px, pickup_px)
                self._logger.info(
                    "[EXECUTE] source=workpiece_layer cleaned_contour_px=%d canonical_px=%d settings=%s",
                    len(raw_pts_px),
                    len(pts_px),
                    settings,
                )
                if pickup_px is not None:
                    raw_robot_pts = self._transform_to_robot(raw_pts_px, settings)
                    if raw_robot_pts:
                        pickup_rz_source_path = [list(pt) for pt in raw_robot_pts]
                        pickup_rz_source_contour = [list(pt) for pt in raw_robot_pts]
                robot_pts = self._transform_to_robot(pts_px, settings)
                if robot_pts:
                    robot_paths.append((robot_pts, settings, "Workpiece", pts_px))
        else:
            self._logger.debug(f"USING SPRAY PATTERN")
            for pattern_type in ("Contour", "Fill"):
                for i, pattern in enumerate(spray_pattern.get(pattern_type, [])):
                    contour_arr = pattern.get("contour", [])
                    settings = dict(pattern.get("settings", {}) or {})
                    settings["height_mm"] = workpiece_height_mm
                    if not isinstance(contour_arr, np.ndarray):
                        contour_arr = np.array(contour_arr, dtype=np.float32)
                    if contour_arr.size == 0:
                        continue
                    pts_px = contour_arr.reshape(-1, 2)
                    self._logger.info("[EXECUTE] source=sprayPattern.%s[%d] pixel_points=%d settings=%s", pattern_type,
                                      i, len(pts_px), settings)
                    robot_pts = self._transform_to_robot(pts_px, settings)
                    if robot_pts:
                        robot_paths.append((robot_pts, settings, pattern_type, pts_px))

        if not robot_paths:
            raise ValueError("No executable paths after transformation")

        total_spline_pts = 0
        sampled_paths: list[list[list[float]]] = []
        raw_paths: list[list[list[float]]] = []
        raw_pixel_paths: list[list[list[float]]] = []
        raw_homography_paths: list[list[list[float]]] = []
        prepared_paths: list[list[list[float]]] = []
        curve_paths: list[list[list[float]]] = []
        execution_jobs: list[dict] = []
        debug_heading_marker_threshold_deg = PATH_TANGENT_HEADING_DEADBAND_DEG

        for path_pts, settings, pattern_type, pts_px in robot_paths:
            raw_paths.append([list(pt) for pt in path_pts])
            raw_pixel_paths.append([
                [float(point[0]), float(point[1])]
                for point in np.asarray(pts_px, dtype=float).reshape(-1, 2)
            ])
            raw_homography_paths.append(
                self._homography_preview_strategy.convert(
                    pts_px,
                    settings,
                    segment_config=self._segment_config,
                    z_min=self._z_min,
                    base_position=self._resolve_base_position(),
                    transformer=self._current_transformer(),
                    resolver=self._current_resolver(),
                    pixel_height_compensation_fn=self._pixel_height_compensation_fn,
                    logger=self._logger,
                )
            )
            vel = _safe_float(settings.get("velocity"), 60.0)
            acc = _safe_float(settings.get("acceleration"), 30.0)
            preprocess_spacing_mm, interpolation_spacing_mm, dense_sampling_factor, execution_spacing_mm = _resolve_segment_interpolation_settings(
                settings)
            tangent_lookahead_distance_mm, tangent_heading_deadband_deg = _resolve_segment_tangent_settings(settings)
            debug_heading_marker_threshold_deg = tangent_heading_deadband_deg
            input_densify_spacing_mm = _auto_input_densify_spacing(path_pts, interpolation_spacing_mm)
            interpolation_method = "linear" if _is_closed_contour(path_pts) else "pchip"

            self._logger.debug(f"INTERPOLATION METHOD {interpolation_method}")

            """BUILD THE INTERPOLATION PIPELINE"""
            pipeline = ContourPathPipeline(
                preprocess=PreprocessConfig(
                    min_spacing=preprocess_spacing_mm,
                    max_segment_length=input_densify_spacing_mm,
                    noise_method="none",
                    noise_strength=0.0,
                ),
                interpolation=InterpolationConfig(
                    method=interpolation_method,
                    output_spacing=interpolation_spacing_mm,
                    dense_sampling_factor=dense_sampling_factor,
                )
            )

            """RUN THE INTERPOLATION PIPELINE"""
            pipeline_result = pipeline.run(np.asarray(path_pts, dtype=float)[:, :2])

            prepared_xy = pipeline_result.prepared
            curve_xy = pipeline_result.curve

            """ADD HEADING SUPPORT"""
            sampled_xy = _densify_xy_preserving_anchors(
                prepared_xy,
                config._HEADING_SUPPORT_SPACING_MM,
            )

            tangent_boundary_xy = _sharp_tangent_boundary_xy(prepared_xy)

            self._logger.info(
                "[EXECUTE] Dense tangent support: pattern=%s method=%s prepared=%d dense=%d spacing=%.3fmm sharp_boundaries=%d",
                pattern_type,
                interpolation_method,
                len(prepared_xy),
                len(sampled_xy),
                config._HEADING_SUPPORT_SPACING_MM,
                len(tangent_boundary_xy),
            )

            if len(tangent_boundary_xy):
                self._logger.info(
                    "[EXECUTE] Sharp tangent boundaries XY: %s",
                    [
                        [round(float(point[0]), 3), round(float(point[1]), 3)]
                        for point in tangent_boundary_xy
                    ],
                )

            prepared_path = rebuild_pose_path_from_xy(
                prepared_xy, path_pts, self._rz_mode,
                tangent_lookahead_distance_mm=tangent_lookahead_distance_mm,
                tangent_heading_deadband_deg=tangent_heading_deadband_deg,
            )

            curve_path = rebuild_pose_path_from_xy(
                curve_xy, path_pts, self._rz_mode,
                tangent_lookahead_distance_mm=tangent_lookahead_distance_mm,
                tangent_heading_deadband_deg=tangent_heading_deadband_deg,
            )

            sampled_path = rebuild_pose_path_from_xy(
                sampled_xy, path_pts, self._rz_mode,
                tangent_lookahead_distance_mm=tangent_lookahead_distance_mm,
                tangent_heading_deadband_deg=tangent_heading_deadband_deg,
                tangent_boundary_xy=tangent_boundary_xy,
            )

            execution_anchor_xy = _merge_unique_xy_points(
                np.asarray(path_pts, dtype=float)[:, :2],
                tangent_boundary_xy,
            )

            self._logger.info(
                "[EXECUTE] Execution resampling preserve anchors: contour=%d sharp_boundaries=%d merged=%d",
                len(path_pts),
                len(tangent_boundary_xy),
                len(execution_anchor_xy),
            )

            execution_spline = _resample_execution_path(
                sampled_path,
                target_spacing_mm=execution_spacing_mm,
                preserve_waypoint_xy=execution_anchor_xy,
            )

            total_spline_pts += len(execution_spline)
            prepared_paths.append([list(pt) for pt in prepared_path])
            curve_paths.append([list(pt) for pt in curve_path])
            sampled_paths.append([list(pt) for pt in sampled_path])

            if pickup_px is not None and pickup_xy is None:
                pickup_camera_xy = self._transform_single_pixel_to_robot(
                    float(pickup_px[0]), float(pickup_px[1]),
                    {"height_mm": workpiece_height_mm, **merged},
                    target_point_name=self._target_point_name,
                    frame_name=self._calibration_frame_name,
                )

                if use_workpiece_layer and pickup_rz_source_contour and robot_paths:
                    pickup_rz = compute_pickup_rz_from_robot_contour_with_direction(
                        pickup_rz_source_contour,
                        robot_paths[0][0],
                    )

                    self._logger.info(
                        "[PICKUP_RZ] method=contour_axis_directed pickup_px=(%.3f, %.3f) pickup_camera_xy=(%.3f, %.3f) pickup_rz=%.3f contour_pts=%d path_pts=%d",
                        float(pickup_px[0]),
                        float(pickup_px[1]),
                        float(pickup_camera_xy[0]),
                        float(pickup_camera_xy[1]),
                        float(pickup_rz),
                        len(pickup_rz_source_contour),
                        len(robot_paths[0][0]),
                    )
                else:
                    pickup_rz_path = pickup_rz_source_path or execution_spline
                    pickup_rz = compute_pickup_rz_from_robot_path(pickup_rz_path, pickup_camera_xy)
                    self._logger.info(
                        "[PICKUP_RZ] method=path_tangent pickup_px=(%.3f, %.3f) pickup_camera_xy=(%.3f, %.3f) pickup_rz=%.3f path_pts=%d",
                        float(pickup_px[0]),
                        float(pickup_px[1]),
                        float(pickup_camera_xy[0]),
                        float(pickup_camera_xy[1]),
                        float(pickup_rz),
                        len(pickup_rz_path),
                    )

                raw_pickup_rz = float(pickup_rz)
                measured_delta = unwrap_degrees(pickup_reference_rz, raw_pickup_rz) - pickup_reference_rz
                signed_pickup_axis = pickup_reference_rz + self._pickup_axis_alignment_sign * measured_delta
                pickup_rz = nearest_axis_equivalent_degrees(pickup_reference_rz, signed_pickup_axis)

                if abs(pickup_rz - raw_pickup_rz) > 1e-9:
                    self._logger.info(
                        "[PICKUP_RZ] axis_equivalent_normalized raw=%.3f reference=%.3f sign=%.0f selected=%.3f",
                        raw_pickup_rz,
                        float(pickup_reference_rz),
                        self._pickup_axis_alignment_sign,
                        float(pickup_rz),
                    )

                pickup_xy = self._transform_single_pixel_to_robot(
                    float(pickup_px[0]), float(pickup_px[1]),
                    {"height_mm": workpiece_height_mm, **merged},
                    target_point_name=self._pickup_target_point_name,
                    frame_name=self._calibration_frame_name,
                    rz_override=pickup_rz,
                )

                self._logger.info(
                    "[PICKUP_RZ] pickup point resolved at pickup_rz=%.3f pickup_xy=(%.3f, %.3f)",
                    float(pickup_rz),
                    float(pickup_xy[0]),
                    float(pickup_xy[1]),
                )

            segment_pivot_offset_mm = _safe_float(
                settings.get("offset"),
                default_pivot_offset_mm,
            )

            execution_jobs.append(
                {
                    "path": [list(pt) for pt in sampled_path],
                    "execution_path": [list(pt) for pt in execution_spline],
                    "vel": vel,
                    "acc": acc,
                    "pattern_type": pattern_type,
                    "use_workpiece_layer": bool(use_workpiece_layer),
                    "workpiece_height_mm": float(workpiece_height_mm),
                    "pivot_offset_mm": float(segment_pivot_offset_mm),
                    "pickup_xy": [float(pickup_xy[0]), float(pickup_xy[1])] if pickup_xy is not None else None,
                    "pickup_rz": float(pickup_rz),
                    "pickup_target_point_name": pickup_target_name,
                    "pickup_target_offset_x": float(pickup_target_offset_x),
                    "pickup_target_offset_y": float(pickup_target_offset_y),
                    "pickup_reference_rz": float(pickup_reference_rz),
                    "execution_target_point_name": execution_target_name,
                    "execution_target_offset_x": float(execution_target_offset_x),
                    "execution_target_offset_y": float(execution_target_offset_y),
                    "execution_reference_rz": float(execution_reference_rz),
                }
            )

        if not skip_debug_plot:
            self._save_interpolated_path_debug_plot(
                raw_paths=raw_paths,
                prepared_paths=prepared_paths,
                curve_paths=curve_paths,
                sampled_paths=sampled_paths,
                execution_paths=[
                    [list(point) for point in job.get("execution_path", [])]
                    for job in execution_jobs
                ],
                heading_marker_threshold_deg=debug_heading_marker_threshold_deg,
            )

        return WorkpieceExecutionPlan(
            workpiece=dict(merged),
            raw_paths=raw_paths,
            prepared_paths=prepared_paths,
            curve_paths=curve_paths,
            sampled_paths=sampled_paths,
            execution_jobs=execution_jobs,
            total_spline_pts=total_spline_pts,
            raw_pixel_paths=raw_pixel_paths,
            raw_homography_paths=raw_homography_paths,
        )

    def _save_interpolated_path_debug_plot(
            self,
            *,
            raw_paths: list[list[list[float]]],
            prepared_paths: list[list[list[float]]],
            curve_paths: list[list[list[float]]],
            sampled_paths: list[list[list[float]]],
            execution_paths: list[list[list[float]]],
            heading_marker_threshold_deg: float,
    ) -> None:
        """Persist a multi-panel debug plot comparing all path representations.

        Only writes when *debug_plot_dir* is configured. Catches and logs all failures
        silently (debug level) so failures never block execution.
        """
        if not self._debug_plot_dir:
            return
        try:
            from src.engine.robot.path_interpolation.new_interpolation.debug_plotting import (
                plot_trajectory_debug,
            )

            image_path = plot_trajectory_debug(
                raw_paths=raw_paths,
                prepared_paths=prepared_paths,
                curve_paths=curve_paths,
                sampled_paths=sampled_paths,
                execution_paths=execution_paths,
                save_dir=self._debug_plot_dir,
                heading_marker_threshold_deg=heading_marker_threshold_deg,
            )
            if image_path:
                self._logger.info("[EXECUTE] Saved interpolated path debug plot to %s", image_path)
        except Exception:
            self._logger.debug("[EXECUTE] Failed to save interpolated path debug plot", exc_info=True)

    def _transform_to_robot(self, pts_px: np.ndarray, settings: dict) -> list:
        """Convert pixel-space contour points to 6-DOF robot poses (X, Y, Z, RX, RY, RZ).

        Two modes (controlled by *pixel_to_mm_mode*):
          - geometry_ppm_anchor: resolve a single anchor through the calibration resolver,
            then offset all other points via a homography-derived direction basis +
            geometry PPM scale.
          - homography_residual: resolve every point individually through the resolver.

        Falls back to a simple Transformer (or raw pixel coords) when no resolver is available.
        """

        try:
            defaults = self._segment_config.schema.get_defaults()
            spray_height = float(
                str(settings.get("spraying_height", defaults.get("spraying_height", "0"))).replace(",", ""))
            base_position = self._resolve_base_position()
            base_z = base_position[2] + spray_height if base_position is not None else self._z_min + spray_height
            rz_offset = float(settings.get("rz_angle", defaults.get("rz_angle", "0")))
            workpiece_height_mm = _safe_float(settings.get("height_mm"), config._DEFAULT_WORKPIECE_HEIGHT_MM)
        except (ValueError, TypeError):
            raise ValueError("Invalid segment settings: spraying_height and rz_angle must be numbers")
        rx, ry = _base_orientation_xy(base_position)
        robot_xy_points: list[tuple[float, float]] = []
        compensated_pts_px = np.asarray(pts_px, dtype=np.float64).copy()

        if callable(self._pixel_height_compensation_fn) and abs(workpiece_height_mm) > 1e-9:
            try:
                compensation_dx_px, compensation_dy_px = self._pixel_height_compensation_fn(workpiece_height_mm)
                compensated_pts_px[:, 0] -= float(compensation_dx_px)
                compensated_pts_px[:, 1] -= float(compensation_dy_px)
                self._logger.info(
                    "[EXECUTE] Applied pixel height compensation: height_mm=%.3f pixel_delta=(%.6f, %.6f)",
                    workpiece_height_mm,
                    float(compensation_dx_px),
                    float(compensation_dy_px),
                )
            except Exception:
                self._logger.exception("[EXECUTE] Failed to apply pixel height compensation")

        resolver = self._current_resolver()
        transformer = self._current_transformer()

        if resolver is not None:
            context = PixelToMmContext(
                base_z=base_z,
                rz_offset=rz_offset,
                rx=rx,
                ry=ry,
                target_point_name=self._target_point_name,
                calibration_frame_name=self._calibration_frame_name,
                mode_name=self._pixel_to_mm_mode,
                logger=self._logger,
                geometry_scale_cache=self._geometry_scale_cache,
            )
            geometry_result = (
                self._geometry_ppm_strategy.convert(
                    compensated_pts_px,
                    resolver=resolver,
                    context=context,
                )
                if self._pixel_to_mm_mode == config.PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR
                else None
            )
            if geometry_result is not None:
                seeded_results, robot_xy_points = geometry_result
            else:
                seeded_results, robot_xy_points = self._homography_residual_strategy.convert(
                    compensated_pts_px,
                    resolver=resolver,
                    context=context,
                )
        else:
            seeded_results = None
            if transformer is None or not transformer.is_available():
                self._logger.warning("[EXECUTE] No calibration transformer — using raw pixel coords")
            for px, py in compensated_pts_px:
                if transformer is not None and transformer.is_available():
                    rx_coord, ry_coord = transformer.transform(float(px), float(py))
                else:
                    rx_coord, ry_coord = float(px), float(py)
                robot_xy_points.append((float(rx_coord), float(ry_coord)))

        from src.engine.robot.path_preparation.geometry import compute_path_aligned_rz_degrees

        if self._rz_mode == "path_tangent":
            rz_values = compute_path_aligned_rz_degrees(robot_xy_points, base_rz_offset_degrees=rz_offset)
        else:
            rz_values = [float(rz_offset) for _ in robot_xy_points]

        if seeded_results is not None:
            result = [
                [float(x), float(y), float(seed.z), rx, ry, float(rz)]
                for seed, (x, y), rz in zip(seeded_results, robot_xy_points, rz_values)
            ]
        else:
            result = [
                [float(x), float(y), float(base_z), rx, ry, float(rz)]
                for (x, y), rz in zip(robot_xy_points, rz_values)
            ]
        if result:
            self._logger.debug(
                "[EXECUTE] RZ mode=%s first headings=%s",
                self._rz_mode,
                [round(float(point[5]), 3) for point in result[: min(5, len(result))]],
            )
        return result

    def _extract_pickup_pixel(self, merged: dict) -> tuple[float, float] | None:
        """Get the pickup point in pixel coords from the workpiece dict.

        Priority:
          1. Explicit *pickupPoint* key (string "x,y", list [x, y], or dict {"x":.., "y":..}).
          2. Contour image-moment centroid.
          3. Contour XY mean.
        Returns None when no contour exists.
        """
        pickup_point = (merged or {}).get("pickupPoint")
        parsed_pickup = self._parse_pickup_point(pickup_point)
        if parsed_pickup is not None:
            return parsed_pickup

        contour_arr = np.asarray((merged or {}).get("contour", []), dtype=np.float32)
        if contour_arr.size == 0:
            return None
        contour_pts = contour_arr.reshape(-1, 1, 2)
        moments = cv2.moments(contour_pts)
        if abs(float(moments.get("m00", 0.0))) > 1e-9:
            cx = float(moments["m10"] / moments["m00"])
            cy = float(moments["m01"] / moments["m00"])
            return cx, cy
        flat_pts = contour_pts.reshape(-1, 2)
        return float(np.mean(flat_pts[:, 0])), float(np.mean(flat_pts[:, 1]))

    @staticmethod
    def _parse_pickup_point(value) -> tuple[float, float] | None:
        """Parse an explicit pickup point from string ("x,y"), list/tuple, or dict ({"x":., "y":.})."""
        if value is None:
            return None

        if isinstance(value, str):
            try:
                x_str, y_str = value.split(",", 1)
                return float(x_str), float(y_str)
            except (TypeError, ValueError):
                return None

        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                return float(value[0]), float(value[1])
            except (TypeError, ValueError):
                return None

        if isinstance(value, dict):
            try:
                return float(value["x"]), float(value["y"])
            except (KeyError, TypeError, ValueError):
                return None

        return None

    def _transform_single_pixel_to_robot(
            self,
            px: float,
            py: float,
            settings: dict,
            *,
            target_point_name: str | None = None,
            frame_name: str = "",
            rz_override: float | None = None,
    ) -> tuple[float, float]:
        """Transform a single pixel coordinate to robot XY, with optional height compensation and RZ override.

        Uses the calibration resolver when available; falls back to the transformer
        or raw pixel coordinates. The *rz_override* replaces the segment-level rz_angle
        (used for the final pickup-point transform after the RZ has been computed).
        """
        workpiece_height_mm = _safe_float(settings.get("height_mm"), config._DEFAULT_WORKPIECE_HEIGHT_MM)
        compensated_px = float(px)
        compensated_py = float(py)

        if callable(self._pixel_height_compensation_fn) and abs(workpiece_height_mm) > 1e-9:
            dx_px, dy_px = self._pixel_height_compensation_fn(workpiece_height_mm)
            compensated_px -= float(dx_px)
            compensated_py -= float(dy_px)

        try:
            defaults = self._segment_config.schema.get_defaults()
            spray_height = float(
                str(settings.get("spraying_height", defaults.get("spraying_height", "0"))).replace(",", ""))
            rz_offset = float(settings.get("rz_angle", defaults.get("rz_angle", "0")))
        except (ValueError, TypeError):
            spray_height = 0.0
            rz_offset = 0.0

        if rz_override is not None:
            rz_offset = float(rz_override)

        base_position = self._resolve_base_position()
        base_z = base_position[2] + spray_height if base_position is not None else self._z_min + spray_height
        rx, ry = _base_orientation_xy(base_position)

        resolver = self._current_resolver()
        transformer = self._current_transformer()

        if resolver is not None:
            from src.engine.robot.targeting import VisionPoseRequest

            resolved_target_name = str(target_point_name or self._target_point_name or "").strip().lower()
            target_point = resolver.registry.by_name(resolved_target_name)

            vision_request = VisionPoseRequest(
                x_pixels=compensated_px,
                y_pixels=compensated_py,
                z_mm=base_z,
                rz_degrees=rz_offset,
                rx_degrees=rx,
                ry_degrees=ry
            )

            result = resolver.resolve(
                vision_request,
                target_point,
                frame=str(frame_name or "").strip().lower(),
            )
            return float(result.final_xy[0]), float(result.final_xy[1])

        if transformer is None or not transformer.is_available():
            return compensated_px, compensated_py

        rx_coord, ry_coord = transformer.transform(compensated_px, compensated_py)
        return float(rx_coord), float(ry_coord)

    def _resolve_base_position(self) -> Optional[list[float]]:
        """Return the current robot base position (X, Y, Z, RX, RY, RZ) from the injected provider.

        Returns None when the provider is unset, the call fails, or the returned
        position has fewer than 3 elements (no Z available).
        """
        provider = self._base_position_provider

        if provider is None:
            return None

        try:
            position = provider()
        except Exception:
            self._logger.debug("Path preparation base position lookup failed", exc_info=True)
            return None

        if not position or len(position) < 3:
            return None

        try:
            return [float(position[i]) for i in range(6 if len(position) >= 6 else len(position))]
        except (TypeError, ValueError):
            return None


def _base_orientation_xy(base_position: Optional[list[float]]) -> tuple[float, float]:
    """Extract RX and RY from a base-position 6-DOF vector, defaulting to (180, 0) when unavailable."""
    if base_position is not None and len(base_position) >= 5:
        return float(base_position[3]), float(base_position[4])

    return 180.0, 0.0

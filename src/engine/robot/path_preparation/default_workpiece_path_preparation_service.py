from __future__ import annotations

import json
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, Optional
import logging

import cv2
import numpy as np

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
    _orient_contour_like_original,
)
from src.engine.robot.path_preparation.i_workpiece_path_preparation_service import IWorkpiecePathPreparationService
from src.engine.robot.calibration.robot_calibration.calibration_report import derive_calibration_artifact_paths
_EXECUTION_INTERPOLATION_SPACING_MM = 10.0
_EXECUTION_MIN_PREPROCESS_SPACING_MM = 2.5
_EXECUTION_DENSE_SAMPLING_FACTOR = 0.25
_EXECUTION_OUTPUT_SPACING_SCALE = 0.75
_EXECUTION_MIN_OUTPUT_SPACING_MM = 6.0
_EXECUTION_DEFAULT_OUTPUT_SPACING_MM = max(
    _EXECUTION_MIN_OUTPUT_SPACING_MM,
    _EXECUTION_INTERPOLATION_SPACING_MM * _EXECUTION_OUTPUT_SPACING_SCALE,
)
_AUTO_DENSIFY_TRIGGER_RATIO = 2.5
_AUTO_DENSIFY_TARGET_RATIO = 1.25
_DEFAULT_WORKPIECE_HEIGHT_MM = 0.0
_SEGMENT_PREPROCESS_MIN_SPACING_KEY = "preprocess_min_spacing_mm"
_SEGMENT_INTERPOLATION_SPACING_KEY = "interpolation_spacing_mm"
_SEGMENT_DENSE_SAMPLING_FACTOR_KEY = "dense_sampling_factor"
_SEGMENT_EXECUTION_SPACING_KEY = "execution_spacing_mm"
_SEGMENT_TANGENT_LOOKAHEAD_DISTANCE_KEY = "path_tangent_lookahead_mm"
_SEGMENT_TANGENT_DEADBAND_KEY = "path_tangent_deadband_deg"
_CANONICALIZE_WORKPIECE_LAYER_CONTOUR = True
_TEMPORARILY_SKIP_CONTOUR_INTERPOLATION = False


@dataclass(frozen=True)
class WorkpieceExecutionPlan:
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
        return [
            [list(point) for point in (job.get("execution_path") or job.get("path") or [])]
            for job in self.execution_jobs
        ]


def _safe_float(value, default: float) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _resample_execution_path(
    path: list[list[float]],
    target_spacing_mm: float,
) -> list[list[float]]:
    if len(path) < 3:
        return [list(point) for point in path]

    target_spacing_mm = max(1.0, float(target_spacing_mm))
    resampled: list[list[float]] = [list(path[0])]
    carry_mm = 0.0

    for i in range(len(path) - 1):
        start = np.array(path[i], dtype=float)
        end = np.array(path[i + 1], dtype=float)
        segment = end[:3] - start[:3]
        seg_len = float(np.linalg.norm(segment))
        if seg_len <= 1e-9:
            continue

        distance_along = target_spacing_mm - carry_mm if carry_mm > 1e-9 else target_spacing_mm
        while distance_along < seg_len - 1e-9:
            ratio = distance_along / seg_len
            point = (start + ratio * (end - start)).tolist()
            if any(abs(float(a) - float(b)) > 1e-9 for a, b in zip(resampled[-1], point)):
                resampled.append(point)
            distance_along += target_spacing_mm

        remaining = seg_len - (distance_along - target_spacing_mm)
        carry_mm = 0.0 if remaining >= target_spacing_mm - 1e-9 else remaining

    if any(abs(float(a) - float(b)) > 1e-9 for a, b in zip(resampled[-1], path[-1])):
        resampled.append(list(path[-1]))
    return resampled


def _resolve_segment_interpolation_settings(settings: dict) -> tuple[float, float, float, float]:
    preprocess_spacing_mm = max(
        0.1,
        _safe_float(settings.get(_SEGMENT_PREPROCESS_MIN_SPACING_KEY), _EXECUTION_MIN_PREPROCESS_SPACING_MM),
    )
    interpolation_spacing_mm = max(
        0.5,
        _safe_float(settings.get(_SEGMENT_INTERPOLATION_SPACING_KEY), _EXECUTION_INTERPOLATION_SPACING_MM),
    )
    dense_sampling_factor = max(
        0.05,
        _safe_float(settings.get(_SEGMENT_DENSE_SAMPLING_FACTOR_KEY), _EXECUTION_DENSE_SAMPLING_FACTOR),
    )
    execution_spacing_mm = max(
        1.0,
        _safe_float(settings.get(_SEGMENT_EXECUTION_SPACING_KEY), _EXECUTION_DEFAULT_OUTPUT_SPACING_MM),
    )
    return preprocess_spacing_mm, interpolation_spacing_mm, dense_sampling_factor, execution_spacing_mm


def _resolve_segment_tangent_settings(settings: dict) -> tuple[float, float]:
    lookahead_distance_mm = max(
        1.0,
        _safe_float(settings.get(_SEGMENT_TANGENT_LOOKAHEAD_DISTANCE_KEY), PATH_TANGENT_LOOKAHEAD_DISTANCE_MM),
    )
    heading_deadband_deg = max(
        0.0,
        _safe_float(settings.get(_SEGMENT_TANGENT_DEADBAND_KEY), PATH_TANGENT_HEADING_DEADBAND_DEG),
    )
    return lookahead_distance_mm, heading_deadband_deg


def _save_contour_reordering_debug_plot(
    original_points: np.ndarray,
    reordered_points: np.ndarray,
    pickup_point: tuple[float, float] | None = None,
    *,
    debug_dir: str = "/home/ilv/Desktop/robot_app_platform/src/bootstrap/debug_plots",
) -> None:
    """Save an overlay image showing original vs canonicalized contour ordering."""
    try:
        original = np.asarray(original_points, dtype=np.float64)
        reordered = np.asarray(reordered_points, dtype=np.float64)
        if original.ndim != 2 or reordered.ndim != 2 or len(original) < 2 or len(reordered) < 2:
            return

        all_points = np.vstack([original[:, :2], reordered[:, :2]])
        min_xy = np.min(all_points, axis=0)
        max_xy = np.max(all_points, axis=0)
        pad = 30.0
        span = np.maximum(max_xy - min_xy, np.array([1.0, 1.0], dtype=np.float64))
        scale = min(900.0 / float(span[0]), 700.0 / float(span[1]))

        def _to_canvas(points: np.ndarray) -> np.ndarray:
            pts = np.asarray(points[:, :2], dtype=np.float64)
            pts = (pts - min_xy) * scale + pad
            pts[:, 1] = (span[1] * scale + 2.0 * pad) - pts[:, 1]
            return np.rint(pts).astype(np.int32).reshape(-1, 1, 2)

        canvas_w = int(np.ceil(span[0] * scale + 2.0 * pad))
        canvas_h = int(np.ceil(span[1] * scale + 2.0 * pad))
        canvas = np.full((max(canvas_h, 100), max(canvas_w, 100), 3), 255, dtype=np.uint8)

        original_canvas = _to_canvas(original)
        reordered_canvas = _to_canvas(reordered)

        cv2.polylines(canvas, [original_canvas], True, (0, 0, 255), 2)
        cv2.polylines(canvas, [reordered_canvas], True, (0, 180, 0), 2)
        cv2.circle(canvas, tuple(original_canvas[0, 0]), 6, (0, 0, 180), -1)
        cv2.circle(canvas, tuple(reordered_canvas[0, 0]), 6, (0, 180, 0), -1)
        cv2.putText(canvas, "Original start", tuple(original_canvas[0, 0] + np.array([8, -8])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 180), 1, cv2.LINE_AA)
        cv2.putText(canvas, "Reordered start", tuple(reordered_canvas[0, 0] + np.array([8, 18])), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 120, 0), 1, cv2.LINE_AA)
        if pickup_point is not None:
            pickup_canvas = _to_canvas(np.asarray([[float(pickup_point[0]), float(pickup_point[1])]], dtype=np.float64))
            px, py = tuple(pickup_canvas[0, 0])
            cv2.drawMarker(canvas, (int(px), int(py)), (200, 0, 200), cv2.MARKER_CROSS, 18, 2)
            cv2.putText(
                canvas,
                f"Pickup centroid ({float(pickup_point[0]):.1f}, {float(pickup_point[1]):.1f})",
                (int(px) + 8, int(py) - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (140, 0, 140),
                1,
                cv2.LINE_AA,
            )

        os.makedirs(debug_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(debug_dir, f"contour_reorder_debug_{timestamp}.png")
        cv2.imwrite(path, canvas)
        _logger.info("[EXECUTE] Saved contour reorder debug plot to: %s", path)
    except Exception:
        _logger.debug("[EXECUTE] Failed to save contour reorder debug plot", exc_info=True)


def _save_contour_canonicalization_steps_debug_plot(
    original_points: np.ndarray,
    pickup_point: tuple[float, float] | None = None,
    *,
    debug_dir: str = "/home/ilv/Desktop/robot_app_platform/src/bootstrap/debug_plots",
) -> None:
    """Save each contour canonicalization step used before pixel-to-mm conversion."""
    try:
        original = np.asarray(original_points, dtype=np.float64)
        if original.ndim != 2 or original.shape[1] < 2 or len(original) < 2:
            return

        stages: list[tuple[str, np.ndarray]] = [("0 raw input", original[:, :2].copy())]
        contour = original[:, :2].copy()

        removed_close = False
        if len(contour) >= 2 and np.linalg.norm(contour[0] - contour[-1]) <= 1e-6:
            contour = contour[:-1]
            removed_close = True
        stages.append(("1 remove duplicate close" if removed_close else "1 no duplicate close", contour.copy()))

        if len(contour) < 3:
            return

        original_open = contour.copy()
        signed_area = 0.5 * float(
            np.dot(contour[:, 0], np.roll(contour[:, 1], -1))
            - np.dot(contour[:, 1], np.roll(contour[:, 0], -1))
        )
        reversed_winding = signed_area > 0.0
        if reversed_winding:
            contour = contour[::-1].copy()
        stages.append(("2 reverse winding" if reversed_winding else "2 keep winding", contour.copy()))

        start_index = int(np.lexsort((contour[:, 0], contour[:, 1]))[0])
        contour = np.roll(contour, -start_index, axis=0)
        stages.append((f"3 roll start idx {start_index}", contour.copy()))

        oriented = _orient_contour_like_original(contour, original_open)
        orientation_changed = (
            len(oriented) == len(contour)
            and np.linalg.norm(oriented[1] - contour[1]) > 1e-6
        )
        contour = oriented
        stages.append(("4 orient like original" if orientation_changed else "4 keep orientation", contour.copy()))

        closed = False
        if len(contour) >= 3 and np.linalg.norm(contour[0] - contour[-1]) > 1e-9:
            contour = np.vstack([contour, contour[:1]])
            closed = True
        stages.append(("5 explicit close" if closed else "5 already closed", contour.copy()))

        all_points = np.vstack([stage[:, :2] for _, stage in stages if len(stage)])
        min_xy = np.min(all_points, axis=0)
        max_xy = np.max(all_points, axis=0)
        span = np.maximum(max_xy - min_xy, np.array([1.0, 1.0], dtype=np.float64))

        cols = 3
        rows = int(np.ceil(len(stages) / cols))
        cell_w = 420
        cell_h = 340
        pad = 34.0
        canvas = np.full((rows * cell_h, cols * cell_w, 3), 255, dtype=np.uint8)

        def _to_canvas(points: np.ndarray, col: int, row: int) -> np.ndarray:
            pts = np.asarray(points[:, :2], dtype=np.float64)
            scale = min((cell_w - 2.0 * pad) / float(span[0]), (cell_h - 2.0 * pad) / float(span[1]))
            mapped = (pts - min_xy) * scale + pad
            mapped[:, 1] = (span[1] * scale + 2.0 * pad) - mapped[:, 1]
            mapped[:, 0] += col * cell_w
            mapped[:, 1] += row * cell_h
            return np.rint(mapped).astype(np.int32).reshape(-1, 1, 2)

        colors = [
            (190, 30, 30),
            (30, 130, 30),
            (30, 80, 200),
            (200, 110, 20),
            (150, 40, 180),
            (30, 160, 180),
        ]
        for index, (title, points) in enumerate(stages):
            row = index // cols
            col = index % cols
            x0 = col * cell_w
            y0 = row * cell_h
            cv2.rectangle(canvas, (x0, y0), (x0 + cell_w - 1, y0 + cell_h - 1), (220, 220, 220), 1)
            cv2.putText(canvas, title, (x0 + 12, y0 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (20, 20, 20), 1, cv2.LINE_AA)
            cv2.putText(
                canvas,
                f"pts={len(points)} bbox=({float(np.ptp(points[:, 0])):.1f}, {float(np.ptp(points[:, 1])):.1f})",
                (x0 + 12, y0 + 48),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (80, 80, 80),
                1,
                cv2.LINE_AA,
            )
            if len(points) < 2:
                continue
            canvas_points = _to_canvas(points, col, row)
            cv2.polylines(canvas, [canvas_points], False, colors[index % len(colors)], 2)
            cv2.circle(canvas, tuple(canvas_points[0, 0]), 6, (0, 160, 0), -1)
            cv2.circle(canvas, tuple(canvas_points[-1, 0]), 6, (0, 0, 220), -1)
            if pickup_point is not None:
                pickup_canvas = _to_canvas(np.asarray([[float(pickup_point[0]), float(pickup_point[1])]], dtype=np.float64), col, row)
                cv2.drawMarker(canvas, tuple(pickup_canvas[0, 0]), (200, 0, 200), cv2.MARKER_CROSS, 15, 2)

        os.makedirs(debug_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(debug_dir, f"contour_canonicalization_steps_{timestamp}.png")
        cv2.imwrite(path, canvas)
        _logger.info("[EXECUTE] Saved contour canonicalization step plot to: %s", path)
    except Exception:
        _logger.debug("[EXECUTE] Failed to save contour canonicalization step plot", exc_info=True)


def _auto_input_densify_spacing(path_pts: list[list[float]], interpolation_spacing_mm: float) -> float:
    if len(path_pts) < 3:
        return 0.0
    xy = np.asarray(path_pts, dtype=float)[:, :2]
    diffs = np.diff(xy, axis=0)
    seg_lengths = np.linalg.norm(diffs, axis=1)
    seg_lengths = seg_lengths[seg_lengths > 1e-9]
    if seg_lengths.size == 0:
        return 0.0
    max_segment = float(np.max(seg_lengths))
    trigger_spacing = max(float(interpolation_spacing_mm) * _AUTO_DENSIFY_TRIGGER_RATIO, 1.0)
    if max_segment <= trigger_spacing:
        return 0.0
    return max(1.0, float(interpolation_spacing_mm) * _AUTO_DENSIFY_TARGET_RATIO)


def _is_explicitly_closed_path(path_pts: list[list[float]]) -> bool:
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
    ) -> None:
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
        self._geometry_scale_cache: tuple[str, float] | None = None
        try:
            pickup_alignment_sign = float(pickup_axis_alignment_sign)
        except (TypeError, ValueError):
            pickup_alignment_sign = 1.0
        self._pickup_axis_alignment_sign = 1.0 if pickup_alignment_sign >= 0.0 else -1.0

    def _current_transformer(self):
        if self._transformer_getter is not None:
            try:
                return self._transformer_getter()
            except Exception:
                self._logger.debug("Path preparation transformer lookup failed", exc_info=True)
        return self._transformer

    def _current_resolver(self):
        if self._resolver_getter is not None:
            try:
                return self._resolver_getter()
            except Exception:
                self._logger.debug("Path preparation resolver lookup failed", exc_info=True)
        return self._resolver

    def _resolve_target_point_metadata(self, target_point_name: str, frame_name: str) -> tuple[str, float, float, float]:
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

    def build_execution_plan(self, workpiece: dict) -> WorkpieceExecutionPlan:
        from src.engine.robot.path_interpolation.new_interpolation.interpolation_pipeline import (
            ContourPathPipeline,
            InterpolationConfig,
            PreprocessConfig,
            RuckigConfig,
        )

        merged = workpiece
        original_pickup_source = dict(merged)
        if has_valid_contour(merged.get("contour")):
            try:
                original_pickup_source["contour"] = np.array(merged.get("contour", []), dtype=np.float32).copy()
            except Exception:
                original_pickup_source["contour"] = merged.get("contour")
        spray_pattern = merged.get("sprayPattern", {})
        workpiece_height_mm = _safe_float(merged.get("height_mm"), _DEFAULT_WORKPIECE_HEIGHT_MM)
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

        if not contour and not fill:
            if self._execute_from_workpiece_layer and has_valid_contour(merged.get("contour")):
                use_workpiece_layer = True
                self._logger.info("[EXECUTE] No spray patterns found; using workpiece layer for execution")
            else:
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
                if _CANONICALIZE_WORKPIECE_LAYER_CONTOUR and len(raw_pts_px) >= 3:
                    _save_contour_canonicalization_steps_debug_plot(raw_pts_px, pickup_px)
                pts_px = (
                    canonicalize_closed_contour_points(raw_pts_px)
                    if _CANONICALIZE_WORKPIECE_LAYER_CONTOUR
                    else raw_pts_px
                )
                if _CANONICALIZE_WORKPIECE_LAYER_CONTOUR and len(raw_pts_px) >= 3 and len(pts_px) >= 3:
                    _save_contour_reordering_debug_plot(raw_pts_px, pts_px, pickup_px)
                self._logger.info("[EXECUTE] Workpiece: %d pixel points | settings=%s", len(pts_px), settings)
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
                    self._logger.info("[EXECUTE] %s[%d]: %d pixel points | settings=%s", pattern_type, i, len(pts_px), settings)
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

        for path_pts, settings, pattern_type, pts_px in robot_paths:
            raw_paths.append([list(pt) for pt in path_pts])
            raw_pixel_paths.append([
                [float(point[0]), float(point[1])]
                for point in np.asarray(pts_px, dtype=float).reshape(-1, 2)
            ])
            raw_homography_paths.append(self._transform_to_robot_homography_only(pts_px, settings))
            vel = _safe_float(settings.get("velocity"), 60.0)
            acc = _safe_float(settings.get("acceleration"), 30.0)
            preprocess_spacing_mm, interpolation_spacing_mm, dense_sampling_factor, execution_spacing_mm = _resolve_segment_interpolation_settings(settings)
            tangent_lookahead_distance_mm, tangent_heading_deadband_deg = _resolve_segment_tangent_settings(settings)
            input_densify_spacing_mm = _auto_input_densify_spacing(path_pts, interpolation_spacing_mm)
            interpolation_method = "linear" if _is_explicitly_closed_path(path_pts) else "pchip"
            if interpolation_method == "linear":
                self._logger.info(
                    "[EXECUTE] Preserving closed contour geometry with linear resampling: pattern=%s pts=%d",
                    pattern_type,
                    len(path_pts),
                )

            if _TEMPORARILY_SKIP_CONTOUR_INTERPOLATION:
                self._logger.info(
                    "[EXECUTE] Skipping contour interpolation for temporary debug bypass: pattern=%s pts=%d",
                    pattern_type,
                    len(path_pts),
                )
                prepared_path = [list(pt) for pt in path_pts]
                curve_path = [list(pt) for pt in path_pts]
                sampled_path = [list(pt) for pt in path_pts]
                execution_spline = [list(pt) for pt in path_pts]
            else:
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
                    ),
                    ruckig=RuckigConfig(enabled=False),
                )
                pipeline_result = pipeline.run(np.asarray(path_pts, dtype=float)[:, :2])
                prepared_path = rebuild_pose_path_from_xy(
                    pipeline_result.prepared, path_pts, self._rz_mode,
                    tangent_lookahead_distance_mm=tangent_lookahead_distance_mm,
                    tangent_heading_deadband_deg=tangent_heading_deadband_deg,
                )
                curve_path = rebuild_pose_path_from_xy(
                    pipeline_result.curve, path_pts, self._rz_mode,
                    tangent_lookahead_distance_mm=tangent_lookahead_distance_mm,
                    tangent_heading_deadband_deg=tangent_heading_deadband_deg,
                )
                sampled_path = rebuild_pose_path_from_xy(
                    pipeline_result.sampled, path_pts, self._rz_mode,
                    tangent_lookahead_distance_mm=tangent_lookahead_distance_mm,
                    tangent_heading_deadband_deg=tangent_heading_deadband_deg,
                )
                execution_spline = _resample_execution_path(sampled_path, target_spacing_mm=execution_spacing_mm)
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
                    rz_override=0.0,
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
                pickup_contact_rz = 0.0
                pickup_xy = self._transform_single_pixel_to_robot(
                    float(pickup_px[0]), float(pickup_px[1]),
                    {"height_mm": workpiece_height_mm, **merged},
                    target_point_name=self._pickup_target_point_name,
                    frame_name=self._calibration_frame_name,
                    rz_override=pickup_contact_rz,
                )
                self._logger.info(
                    "[PICKUP_RZ] pickup point resolved at contact_rz=%.3f carried_pickup_rz=%.3f pickup_xy=(%.3f, %.3f)",
                    float(pickup_contact_rz),
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

    def _transform_to_robot_homography_only(self, pts_px: np.ndarray, settings: dict) -> list:
        """Return pixel-to-robot points using only the base homography, no residual warp."""
        try:
            defaults = self._segment_config.schema.get_defaults()
            spray_height = float(str(settings.get("spraying_height", defaults.get("spraying_height", "0"))).replace(",", ""))
            base_position = self._resolve_base_position()
            base_z = base_position[2] + spray_height if base_position is not None else self._z_min + spray_height
            rz_offset = float(settings.get("rz_angle", defaults.get("rz_angle", "0")))
        except (ValueError, TypeError):
            return []

        transformer = self._current_transformer()
        resolver = self._current_resolver()
        base_transformer = getattr(resolver, "_base", None) if resolver is not None else transformer
        model = getattr(base_transformer, "_model", None)
        homography_matrix = getattr(model, "homography_matrix", None)
        if homography_matrix is None:
            return []

        pts = np.asarray(pts_px, dtype=np.float64).reshape(-1, 2)
        workpiece_height_mm = _safe_float(settings.get("height_mm"), _DEFAULT_WORKPIECE_HEIGHT_MM)
        if callable(self._pixel_height_compensation_fn) and abs(workpiece_height_mm) > 1e-9:
            try:
                compensation_dx_px, compensation_dy_px = self._pixel_height_compensation_fn(workpiece_height_mm)
                pts = pts.copy()
                pts[:, 0] -= float(compensation_dx_px)
                pts[:, 1] -= float(compensation_dy_px)
            except Exception:
                self._logger.debug("[EXECUTE] Failed to apply pixel height compensation for homography-only debug", exc_info=True)

        xy = cv2.perspectiveTransform(
            pts.astype(np.float32).reshape(-1, 1, 2),
            np.asarray(homography_matrix, dtype=np.float64).reshape(3, 3),
        ).reshape(-1, 2)
        rx, ry = _base_orientation_xy(base_position)
        return [
            [float(x), float(y), float(base_z), float(rx), float(ry), float(rz_offset)]
            for x, y in xy
        ]

    def _transform_to_robot(self, pts_px: np.ndarray, settings: dict) -> list:
        try:
            defaults = self._segment_config.schema.get_defaults()
            spray_height = float(str(settings.get("spraying_height", defaults.get("spraying_height", "0"))).replace(",", ""))
            base_position = self._resolve_base_position()
            base_z = base_position[2] + spray_height if base_position is not None else self._z_min + spray_height
            rz_offset = float(settings.get("rz_angle", defaults.get("rz_angle", "0")))
            workpiece_height_mm = _safe_float(settings.get("height_mm"), _DEFAULT_WORKPIECE_HEIGHT_MM)
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
            from src.engine.robot.targeting import VisionPoseRequest

            geometry_result = self._transform_to_robot_geometry_ppm(
                compensated_pts_px,
                base_z=base_z,
                rz_offset=rz_offset,
                rx=rx,
                ry=ry,
                resolver=resolver,
            )
            if geometry_result is not None:
                seeded_results, robot_xy_points = geometry_result
            else:
                target_point = resolver.registry.by_name(self._target_point_name)
                seeded_results = [
                    resolver.resolve(
                        VisionPoseRequest(
                            float(px),
                            float(py),
                            z_mm=base_z,
                            rz_degrees=rz_offset,
                            rx_degrees=rx,
                            ry_degrees=ry,
                        ),
                        target_point,
                    )
                    for px, py in compensated_pts_px
                ]
                robot_xy_points = [
                    (float(result.final_xy[0]), float(result.final_xy[1]))
                    for result in seeded_results
                ]
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

    def _transform_to_robot_geometry_ppm(
        self,
        compensated_pts_px: np.ndarray,
        *,
        base_z: float,
        rz_offset: float,
        rx: float,
        ry: float,
        resolver,
    ) -> tuple[list, list[tuple[float, float]]] | None:
        points = np.asarray(compensated_pts_px, dtype=np.float64).reshape(-1, 2)
        if points.shape[0] < 2:
            return None

        ppm = self._load_geometry_ppm(resolver)
        if ppm is None or ppm <= 1e-9:
            return None

        anchor_px = self._compute_pixel_anchor(points)
        axes = self._geometry_axes_from_homography(resolver, anchor_px)
        if axes is None:
            self._logger.warning("[EXECUTE] Geometry PPM available but homography direction basis is unavailable")
            return None

        from src.engine.robot.targeting import VisionPoseRequest

        target_point = resolver.registry.by_name(self._target_point_name)
        anchor_result = resolver.resolve(
            VisionPoseRequest(
                float(anchor_px[0]),
                float(anchor_px[1]),
                z_mm=base_z,
                rz_degrees=rz_offset,
                rx_degrees=rx,
                ry_degrees=ry,
            ),
            target_point,
            frame=self._calibration_frame_name,
        )
        anchor_xy = np.asarray(anchor_result.final_xy, dtype=np.float64).reshape(2)
        x_axis, y_axis = axes
        mm_per_px = 1.0 / float(ppm)

        robot_xy = []
        for point_px in points:
            delta_px = point_px - anchor_px
            delta_robot = (delta_px[0] * mm_per_px * x_axis) + (delta_px[1] * mm_per_px * y_axis)
            xy = anchor_xy + delta_robot
            robot_xy.append((float(xy[0]), float(xy[1])))

        seeded_results = [anchor_result for _ in robot_xy]
        if robot_xy:
            xy_arr = np.asarray(robot_xy, dtype=np.float64)
            bbox = np.ptp(xy_arr, axis=0)
            self._logger.info(
                "[EXECUTE] Geometry transform: mode=ppm_anchor ppm=%.6f mm_per_px=%.6f "
                "anchor_px=(%.3f, %.3f) anchor_robot_xy=(%.3f, %.3f) "
                "bbox_robot_mm=(%.3f x %.3f) points=%d",
                float(ppm),
                float(mm_per_px),
                float(anchor_px[0]),
                float(anchor_px[1]),
                float(anchor_xy[0]),
                float(anchor_xy[1]),
                float(bbox[0]),
                float(bbox[1]),
                len(robot_xy),
            )
        return seeded_results, robot_xy

    def _load_geometry_ppm(self, resolver) -> float | None:
        matrix_path = self._resolver_matrix_path(resolver)
        if not matrix_path:
            return None
        if self._geometry_scale_cache is not None and self._geometry_scale_cache[0] == matrix_path:
            return self._geometry_scale_cache[1]

        geometry_path = derive_calibration_artifact_paths(matrix_path)["geometry_scale_path"]
        try:
            with open(geometry_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            ppm = float(payload.get("ppm"))
            if ppm <= 0.0:
                return None
            self._geometry_scale_cache = (matrix_path, ppm)
            self._logger.info("[EXECUTE] Loaded geometry PPM %.6f from %s", ppm, geometry_path)
            return ppm
        except Exception:
            self._logger.debug("[EXECUTE] Geometry PPM artifact unavailable at %s", geometry_path, exc_info=True)
            return None

    @staticmethod
    def _resolver_matrix_path(resolver) -> str | None:
        base = getattr(resolver, "_base", None)
        matrix_path = getattr(base, "_matrix_path", None)
        if matrix_path:
            return str(matrix_path)
        nested_base = getattr(base, "_base", None)
        matrix_path = getattr(nested_base, "_matrix_path", None)
        return str(matrix_path) if matrix_path else None

    @staticmethod
    def _compute_pixel_anchor(points: np.ndarray) -> np.ndarray:
        pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
        if pts.shape[0] >= 3:
            contour = np.ascontiguousarray(pts.astype(np.float32).reshape(-1, 1, 2))
            moments = cv2.moments(contour)
            if abs(float(moments.get("m00", 0.0))) > 1e-9:
                return np.asarray(
                    [
                        float(moments["m10"] / moments["m00"]),
                        float(moments["m01"] / moments["m00"]),
                    ],
                    dtype=np.float64,
                )
        return np.mean(pts, axis=0)

    def _geometry_axes_from_homography(self, resolver, anchor_px: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
        homography_matrix = self._base_homography_matrix(resolver)
        if homography_matrix is None:
            return None

        anchor = np.asarray(anchor_px, dtype=np.float64).reshape(2)
        probe = np.asarray(
            [
                anchor,
                anchor + np.asarray([1.0, 0.0], dtype=np.float64),
                anchor + np.asarray([0.0, 1.0], dtype=np.float64),
            ],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        mapped = cv2.perspectiveTransform(
            probe,
            np.asarray(homography_matrix, dtype=np.float64).reshape(3, 3),
        ).reshape(-1, 2).astype(np.float64)

        frame_obj = resolver.get_frame(self._calibration_frame_name) if self._calibration_frame_name else None
        mapper = getattr(frame_obj, "mapper", None) if frame_obj is not None else None
        if mapper is not None:
            mapped = np.asarray([mapper.map_point(float(x), float(y)) for x, y in mapped], dtype=np.float64)

        x_vec = mapped[1] - mapped[0]
        y_vec = mapped[2] - mapped[0]
        x_norm = float(np.linalg.norm(x_vec))
        y_norm = float(np.linalg.norm(y_vec))
        if x_norm <= 1e-12 or y_norm <= 1e-12:
            return None
        return x_vec / x_norm, y_vec / y_norm

    @staticmethod
    def _base_homography_matrix(resolver):
        base = getattr(resolver, "_base", None)
        model = getattr(base, "_model", None)
        homography_matrix = getattr(model, "homography_matrix", None)
        if homography_matrix is not None:
            return homography_matrix
        nested_base = getattr(base, "_base", None)
        model = getattr(nested_base, "_model", None)
        return getattr(model, "homography_matrix", None)

    def _extract_pickup_pixel(self, merged: dict) -> tuple[float, float] | None:
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
        workpiece_height_mm = _safe_float(settings.get("height_mm"), _DEFAULT_WORKPIECE_HEIGHT_MM)
        compensated_px = float(px)
        compensated_py = float(py)

        if callable(self._pixel_height_compensation_fn) and abs(workpiece_height_mm) > 1e-9:
            dx_px, dy_px = self._pixel_height_compensation_fn(workpiece_height_mm)
            compensated_px -= float(dx_px)
            compensated_py -= float(dy_px)

        try:
            defaults = self._segment_config.schema.get_defaults()
            spray_height = float(str(settings.get("spraying_height", defaults.get("spraying_height", "0"))).replace(",", ""))
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
            result = resolver.resolve(
                VisionPoseRequest(
                    compensated_px,
                    compensated_py,
                    z_mm=base_z,
                    rz_degrees=rz_offset,
                    rx_degrees=rx,
                    ry_degrees=ry,
                ),
                target_point,
                frame=str(frame_name or "").strip().lower(),
            )
            return float(result.final_xy[0]), float(result.final_xy[1])

        if transformer is None or not transformer.is_available():
            return compensated_px, compensated_py

        rx_coord, ry_coord = transformer.transform(compensated_px, compensated_py)
        return float(rx_coord), float(ry_coord)

    def _resolve_base_position(self) -> Optional[list[float]]:
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
    if base_position is not None and len(base_position) >= 5:
        return float(base_position[3]), float(base_position[4])
    return 180.0, 0.0

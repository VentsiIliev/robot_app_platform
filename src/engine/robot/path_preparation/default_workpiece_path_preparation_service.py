from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import os
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from src.engine.robot.path_preparation.debug import _save_contour_canonicalization_steps_debug_plot, \
    _save_contour_reordering_debug_plot

from src.engine.geometry.planar import nearest_axis_equivalent_degrees, unwrap_degrees
from src.engine.robot.path_preparation.geometry import (
    PATH_TANGENT_HEADING_DEADBAND_DEG,
    PATH_TANGENT_LOOKAHEAD_DISTANCE_MM,
    canonicalize_closed_contour_points,
    compute_pickup_rz_from_robot_path,
    compute_pickup_rz_from_initial_paint_segment,
    compute_pickup_rz_from_stable_paint_segment,
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

PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR = config.PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR
PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL = config.PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL



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


def _plot_xy_debug_axis(axis, points: np.ndarray, title: str, x_label: str, y_label: str) -> None:
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    axis.set_title(title)
    axis.set_xlabel(x_label)
    axis.set_ylabel(y_label)
    axis.grid(True, alpha=0.45)
    axis.set_aspect("equal", adjustable="box")
    if len(pts) == 0:
        return
    closed = np.vstack([pts, pts[:1]]) if len(pts) > 2 else pts
    axis.plot(closed[:, 0], closed[:, 1], "-", linewidth=0.8, alpha=0.55, label="contour")
    axis.scatter(pts[:, 0], pts[:, 1], s=8, alpha=0.85, label="all points", zorder=4)
    axis.scatter([pts[0, 0]], [pts[0, 1]], s=45, color="green", edgecolors="black", zorder=5, label="start")
    axis.scatter([pts[-1, 0]], [pts[-1, 1]], s=45, color="red", edgecolors="black", zorder=5, label="end")
    if len(pts) >= 3:
        try:
            rect = cv2.minAreaRect(pts.astype(np.float32).reshape(-1, 1, 2))
            box = cv2.boxPoints(rect)
            box = np.vstack([box, box[:1]])
            axis.plot(box[:, 0], box[:, 1], "--", linewidth=1.0, label="min rect")
        except Exception:
            pass
    axis.legend(loc="best")


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
            source_contour_processor: Optional[Callable[[np.ndarray, dict], np.ndarray | None]] = None,
            contour_processor: Optional[Callable[[list[list[float]], dict], dict | None]] = None,
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
        self._source_contour_processor = source_contour_processor
        self._contour_processor = contour_processor
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

    def _save_contour_pipeline_debug_plot(
            self,
            *,
            label: str,
            before_bezier_px: np.ndarray,
            after_bezier_px: np.ndarray,
            after_conversion_mm: np.ndarray,
    ) -> None:
        """Save before/after source-contour and post-conversion debug plots."""
        if not self._debug_plot_dir:
            return
        try:
            before_px = np.asarray(before_bezier_px, dtype=np.float64).reshape(-1, 2)
            after_px = np.asarray(after_bezier_px, dtype=np.float64).reshape(-1, 2)
            after_mm = np.asarray(after_conversion_mm, dtype=np.float64).reshape(-1, 2)
        except Exception:
            self._logger.debug("Failed to normalize contour pipeline debug data", exc_info=True)
            return
        if len(before_px) == 0 or len(after_px) == 0 or len(after_mm) == 0:
            return

        try:
            os.environ.setdefault("MPLCONFIGDIR", "/tmp/robot_app_platform_matplotlib")
            os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt

            output_dir = Path(self._debug_plot_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            safe_label = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(label or "contour"))
            output_path = output_dir / f"paint_contour_pipeline_{timestamp}_{safe_label}.png"

            fig, axes = plt.subplots(1, 3, figsize=(18, 6))
            _plot_xy_debug_axis(axes[0], before_px, f"Before Bezier ({len(before_px)} px pts)", "Image X (px)", "Image Y (px)")
            _plot_xy_debug_axis(axes[1], after_px, f"After Bezier ({len(after_px)} px pts)", "Image X (px)", "Image Y (px)")
            _plot_xy_debug_axis(axes[2], after_mm, f"After pixel-to-mm ({len(after_mm)} mm pts)", "Robot X (mm)", "Robot Y (mm)")
            axes[0].invert_yaxis()
            axes[1].invert_yaxis()
            fig.suptitle(f"Paint contour pipeline: {label}")
            fig.tight_layout()
            fig.savefig(output_path, dpi=140)
            plt.close(fig)
            self._logger.info("Saved paint contour pipeline debug plot: %s", output_path)
        except Exception:
            self._logger.debug("Failed to save contour pipeline debug plot", exc_info=True)

    def _process_source_contour(self, pts_px: np.ndarray, settings: dict, *, label: str) -> np.ndarray:
        """Apply an optional source-contour processor before pixel-to-mm conversion."""
        points = np.asarray(pts_px, dtype=np.float64).reshape(-1, 2)
        if self._source_contour_processor is None or len(points) < 3:
            return points
        try:
            processed = self._source_contour_processor(points, settings)
        except Exception:
            self._logger.exception("[EXECUTE] Source contour processor failed for %s; using original pixels", label)
            return points
        if processed is None:
            return points
        try:
            processed_points = np.asarray(processed, dtype=np.float64).reshape(-1, 2)
        except Exception:
            self._logger.exception("[EXECUTE] Source contour processor returned invalid contour for %s", label)
            return points
        if len(processed_points) < 3:
            self._logger.warning(
                "[EXECUTE] Source contour processor returned too few points for %s: %d",
                label,
                len(processed_points),
            )
            return points
        self._logger.info(
            "[EXECUTE] Source contour processor: %s input_px=%d processed_px=%d",
            label,
            len(points),
            len(processed_points),
        )
        return processed_points

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
          3. Optional contour processor — injected by the robot system for smoothing/resampling.
          4. Heading reconstruction — constant RZ or path-tangent-aligned.
          5. Pickup resolution — compute the first-segment pickup XY and RZ.
        """
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
                source_before_bezier_px = (
                    canonicalize_closed_contour_points(raw_pts_px)
                    if config._CANONICALIZE_WORKPIECE_LAYER_CONTOUR
                    else raw_pts_px
                )
                pts_px = self._process_source_contour(
                    source_before_bezier_px,
                    settings,
                    label="workpiece_layer",
                )
                if config._CANONICALIZE_WORKPIECE_LAYER_CONTOUR and len(raw_pts_px) >= 3 and len(pts_px) >= 3:
                    _save_contour_reordering_debug_plot(raw_pts_px, pts_px, pickup_px)
                self._logger.info(
                    "[EXECUTE] source=workpiece_layer cleaned_contour_px=%d prepared_px=%d settings=%s",
                    len(raw_pts_px),
                    len(pts_px),
                    settings,
                )
                robot_pts = self._transform_to_robot(pts_px, settings)
                if robot_pts:
                    robot_paths.append((robot_pts, settings, "Workpiece", pts_px, source_before_bezier_px))
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
                    source_before_bezier_px = np.asarray(contour_arr.reshape(-1, 2), dtype=np.float64)
                    pts_px = self._process_source_contour(
                        source_before_bezier_px,
                        settings,
                        label=f"sprayPattern.{pattern_type}[{i}]",
                    )
                    self._logger.info("[EXECUTE] source=sprayPattern.%s[%d] pixel_points=%d settings=%s", pattern_type,
                                      i, len(pts_px), settings)
                    robot_pts = self._transform_to_robot(pts_px, settings)
                    if robot_pts:
                        robot_paths.append((robot_pts, settings, pattern_type, pts_px, source_before_bezier_px))

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

        for path_pts, settings, pattern_type, pts_px, source_before_bezier_px in robot_paths:
            self._save_contour_pipeline_debug_plot(
                label=str(pattern_type),
                before_bezier_px=source_before_bezier_px,
                after_bezier_px=pts_px,
                after_conversion_mm=np.asarray(path_pts, dtype=float)[:, :2],
            )
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
            tangent_lookahead_distance_mm, tangent_heading_deadband_deg = _resolve_segment_tangent_settings(settings)
            debug_heading_marker_threshold_deg = tangent_heading_deadband_deg

            processed_contour = None
            if self._contour_processor is not None:
                try:
                    processed_contour = self._contour_processor(path_pts, settings)
                except Exception:
                    self._logger.exception("[EXECUTE] Contour processor failed; using transformed path")

            if processed_contour:
                prepared_xy = np.asarray(processed_contour.get("prepared_xy"), dtype=float).reshape(-1, 2)
                curve_xy = np.asarray(processed_contour.get("curve_xy", prepared_xy), dtype=float).reshape(-1, 2)
                interpolation_method = str(processed_contour.get("method") or "custom")
                self._logger.info(
                    "[EXECUTE] Contour processor: pattern=%s method=%s input=%d prepared=%d curve=%d",
                    pattern_type,
                    interpolation_method,
                    len(path_pts),
                    len(prepared_xy),
                    len(curve_xy),
                )
            else:
                prepared_xy = np.asarray(path_pts, dtype=float)[:, :2]
                curve_xy = prepared_xy
                interpolation_method = "raw"
                self._logger.info(
                    "[EXECUTE] No contour processor configured: pattern=%s using transformed path points=%d",
                    pattern_type,
                    len(prepared_xy),
                )

            sampled_xy = prepared_xy
            tangent_boundary_xy = np.empty((0, 2), dtype=float)
            self._logger.info(
                "[EXECUTE] Prepared contour output is final: pattern=%s method=%s points=%d",
                pattern_type,
                interpolation_method,
                len(prepared_xy),
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

            execution_spline = [list(point) for point in sampled_path]

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

                if use_workpiece_layer and execution_spline:
                    pickup_rz = compute_pickup_rz_from_initial_paint_segment(
                        execution_spline,
                        pickup_reference_rz,
                    )

                    self._logger.info(
                        "[PICKUP_RZ] method=initial_paint_segment pickup_px=(%.3f, %.3f) pickup_camera_xy=(%.3f, %.3f) pickup_rz=%.3f reference_rz=%.3f path_pts=%d",
                        float(pickup_px[0]),
                        float(pickup_px[1]),
                        float(pickup_camera_xy[0]),
                        float(pickup_camera_xy[1]),
                        float(pickup_rz),
                        float(pickup_reference_rz),
                        len(execution_spline),
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

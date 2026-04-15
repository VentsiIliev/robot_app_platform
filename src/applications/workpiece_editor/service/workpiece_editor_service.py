import logging
import os
from typing import Callable, Optional, TYPE_CHECKING
from datetime import datetime
import cv2
import numpy as np

from src.applications.workpiece_editor.editor_core.config import WorkpieceFormSchema
from src.applications.workpiece_editor.editor_core.config.segment_editor_config import SegmentEditorConfig
from src.applications.workpiece_editor.service import IWorkpieceEditorService
from src.applications.workpiece_editor.editor_core.handlers.SaveWorkpieceHandler import SaveWorkpieceHandler
from src.applications.workpiece_editor.editor_core.adapters.workpiece_adapter import WorkpieceAdapter
from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.vision.i_capture_snapshot_service import ICaptureSnapshotService
from src.applications.workpiece_editor.service.i_workpiece_path_executor import IWorkpiecePathExecutor
from contour_editor.persistence.data.editor_data_model import ContourEditorData

if TYPE_CHECKING:
    from src.engine.robot.targeting import VisionTargetResolver

_logger = logging.getLogger(__name__)
_MAX_PREVIEW_CONTOUR_POINTS = 180


def _derive_interpolation_from_blend_radius(
    blend_radius_mm: float,
) -> tuple[float, float]:
    """Use blend radius as the primary interpolation control when provided."""
    if blend_radius_mm <= 0.0:
        return 10.0, 2.0

    # One-knob mode:
    # - base spacing scales with radius so larger blends use fewer support points
    # - blend sampling stays roughly at half-radius resolution
    effective_adaptive_spacing = max(5.0, blend_radius_mm * 2.0)
    effective_spline_density = 2.0
    return effective_adaptive_spacing, effective_spline_density


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


def _fast_inverse_preview_points(transformer, robot_xy_points: np.ndarray) -> np.ndarray | None:
    if robot_xy_points.size == 0:
        return np.empty((0, 2), dtype=np.float32)

    h_inv = getattr(transformer, "_H_inv", None)
    if h_inv is None:
        model = getattr(transformer, "_model", None)
        homography = getattr(model, "homography_matrix", None)
        if homography is not None:
            try:
                h_inv = np.linalg.inv(np.asarray(homography, dtype=np.float64).reshape(3, 3))
            except Exception:
                h_inv = None

    if h_inv is None:
        return None

    try:
        return cv2.perspectiveTransform(
            np.asarray(robot_xy_points, dtype=np.float32).reshape(-1, 1, 2),
            np.asarray(h_inv, dtype=np.float64),
        ).reshape(-1, 2)
    except Exception:
        return None


def _has_valid_contour(contour) -> bool:
    if contour is None:
        return False
    if isinstance(contour, np.ndarray):
        return int(contour.size) >= 3
    if isinstance(contour, list):
        return len(contour) >= 3
    return False


def _compute_path_aligned_rz_degrees(
    robot_xy_points: list[tuple[float, float]],
    base_rz_offset_degrees: float = 0.0,
) -> list[float]:
    """Compute per-waypoint RZ from local turn accumulation.

    The first segment keeps the base orientation. Each subsequent waypoint adds
    only the turn angle between the previous and next segment. That means the
    robot does not pre-rotate on segment 0->1; it starts rotating from the next
    segment onward, which matches "rotate at the corner while continuing".
    """
    if not robot_xy_points:
        return []
    if len(robot_xy_points) == 1:
        return [float(base_rz_offset_degrees)]
    if len(robot_xy_points) == 2:
        return [float(base_rz_offset_degrees), float(base_rz_offset_degrees)]

    segment_headings: list[float] = []
    for index in range(len(robot_xy_points) - 1):
        current = robot_xy_points[index]
        nxt = robot_xy_points[index + 1]

        dx = float(nxt[0]) - float(current[0])
        dy = float(nxt[1]) - float(current[1])
        if abs(dx) <= 1e-9 and abs(dy) <= 1e-9:
            heading_deg = segment_headings[-1] if segment_headings else 0.0
        else:
            heading_deg = float(np.degrees(np.arctan2(dy, dx)))
            if segment_headings:
                while heading_deg - segment_headings[-1] > 180.0:
                    heading_deg -= 360.0
                while heading_deg - segment_headings[-1] < -180.0:
                    heading_deg += 360.0
        segment_headings.append(heading_deg)

    rz_values: list[float] = [float(base_rz_offset_degrees), float(base_rz_offset_degrees)]
    current_rz = float(base_rz_offset_degrees)
    for index in range(1, len(segment_headings)):
        turn_delta = float(segment_headings[index] - segment_headings[index - 1])
        current_rz += turn_delta
        rz_values.append(current_rz)

    return rz_values[:len(robot_xy_points)]


def _unwrap_degrees(previous: float, current: float) -> float:
    value = float(current)
    prev = float(previous)
    while value - prev > 180.0:
        value -= 360.0
    while value - prev < -180.0:
        value += 360.0
    return value


class WorkpieceEditorService(IWorkpieceEditorService):

    def __init__(self,
                 vision_service,
                 capture_snapshot_service: Optional[ICaptureSnapshotService],
                 save_fn:        Callable[[dict], tuple[bool, str]],
                 update_fn:      Callable[[str, dict], tuple[bool, str]],
                 form_schema:    WorkpieceFormSchema,
                 segment_config: SegmentEditorConfig,
                 id_exists_fn:   Callable[[str], bool] = None,
                 transformer:    Optional[ICoordinateTransformer] = None,
                 resolver:       Optional["VisionTargetResolver"] = None,
                 z_min:          float = 0.0,
                 rz_mode:        str = "constant",
                 debug_dump_dir: Optional[str] = None,
                 robot_service=None,
                 path_executor: Optional[IWorkpiecePathExecutor] = None,
                 target_point_name: str = ""):
        self._vision             = vision_service
        self._capture_snapshot_service = capture_snapshot_service
        self._save_fn            = save_fn
        self._update_fn          = update_fn
        self._id_exists_fn       = id_exists_fn
        self._form_schema        = form_schema
        self._segment_config     = segment_config
        self._transformer        = transformer
        self._resolver           = resolver
        self._z_min              = z_min
        self._rz_mode            = str(rz_mode or "constant").strip().lower()
        self._debug_dump_dir     = debug_dump_dir
        self._robot_service      = robot_service
        self._path_executor      = path_executor
        self._editing_storage_id = None
        self._target_point_name  = str(target_point_name or "").strip().lower()
        self._last_interpolation_preview_contours: list[np.ndarray] = []
        self._last_interpolation_preview_paths: list[list[list[float]]] = []
        self._last_original_preview_paths: list[list[list[float]]] = []
        self._last_pre_smoothed_preview_paths: list[list[list[float]]] = []
        self._last_linear_preview_paths: list[list[list[float]]] = []
        self._last_execution_preview_jobs: list[dict] = []

    def set_editing(self, storage_id) -> None:
        self._editing_storage_id = storage_id
        _logger.debug("WorkpieceEditorService: editing_storage_id=%s", storage_id)

    def _schema(self) -> WorkpieceFormSchema:
        return self._form_schema() if callable(self._form_schema) else self._form_schema

    def get_form_schema(self) -> WorkpieceFormSchema:
        return self._schema()

    def get_segment_config(self) -> SegmentEditorConfig:
        return self._segment_config

    def get_contours(self) -> list:
        if self._capture_snapshot_service is None and self._vision is None:
            _logger.warning("get_contours: no vision service")
            return []
        try:
            if self._capture_snapshot_service is not None:
                return self._capture_snapshot_service.capture_snapshot(source="workpiece_editor").contours
            return self._vision.get_latest_contours()
        except Exception as exc:
            _logger.error("get_contours failed: %s", exc)
            return []

    def save_workpiece(self, data: dict) -> tuple[bool, str]:
        try:
            form_data   = data.get("form_data", {})
            editor_data = data.get("editor_data")
            complete    = self._merge(form_data, editor_data) if editor_data else dict(form_data)
            required    = self._schema().get_required_keys()
            is_valid, errors = SaveWorkpieceHandler.validate_form_data(complete, required)
            if not is_valid:
                return False, f"Validation failed: {', '.join(errors)}"

            if not _has_valid_contour(complete.get("contour")):
                return False, (
                    "No main workpiece contour found.\n"
                    "Use the camera capture button to define the workpiece boundary first."
                )

            if self._editing_storage_id is not None:
                storage_id = self._editing_storage_id
                self._editing_storage_id = None
                return self._update_fn(storage_id, complete)
            else:
                if self._id_exists_fn is not None:
                    wp_id = str(complete.get("workpieceId", "")).strip()
                    if wp_id and self._id_exists_fn(wp_id):
                        return False, f"A workpiece with ID '{wp_id}' already exists"
                return self._save_fn(complete)

        except Exception as exc:
            _logger.exception("save_workpiece failed")
            return False, str(exc)

    def execute_workpiece(self, data: dict) -> tuple[bool, str]:
        from src.engine.robot.path_interpolation.combined_interpolation import interpolate_path_two_stage

        self._last_interpolation_preview_contours = []
        self._last_interpolation_preview_paths = []
        self._last_original_preview_paths = []
        self._last_pre_smoothed_preview_paths = []
        self._last_linear_preview_paths = []
        self._last_execution_preview_jobs = []
        form_data   = data.get("form_data", data)
        editor_data = data.get("editor_data")
        merged      = self._merge(form_data, editor_data) if editor_data else dict(form_data)

        spray_pattern = merged.get("sprayPattern", {})
        if not spray_pattern or not any(spray_pattern.get(k) for k in ("Contour", "Fill")):
            _logger.warning("[EXECUTE] No spray patterns in workpiece data")
            return False, "No spray patterns found — draw Contour or Fill paths first"

        robot_paths = []

        for pattern_type in ("Contour", "Fill"):
            patterns = spray_pattern.get(pattern_type, [])
            if not patterns:
                continue
            _logger.info("[EXECUTE] %d %s pattern(s)", len(patterns), pattern_type)

            for i, pattern in enumerate(patterns):
                contour_arr = pattern.get("contour", [])
                settings    = pattern.get("settings", {})

                if not isinstance(contour_arr, np.ndarray):
                    contour_arr = np.array(contour_arr, dtype=np.float32)
                if contour_arr.size == 0:
                    _logger.warning("[EXECUTE] %s[%d]: empty contour, skipping", pattern_type, i)
                    continue

                pts_px = contour_arr.reshape(-1, 2)
                _logger.info("[EXECUTE] %s[%d]: %d pixel points | settings=%s",
                             pattern_type, i, len(pts_px), settings)

                robot_pts = self._transform_to_robot(pts_px, settings)
                if not robot_pts:
                    _logger.warning("[EXECUTE] %s[%d]: no robot points after transform", pattern_type, i)
                    continue

                robot_paths.append((robot_pts, settings, pattern_type))

        if not robot_paths:
            return False, "No executable paths after transformation"

        total_spline_pts = 0
        preview_paths: list[list[list[float]]] = []
        original_paths: list[list[list[float]]] = []
        pre_smoothed_paths: list[list[list[float]]] = []
        linear_paths: list[list[list[float]]] = []
        for path_pts, settings, pattern_type in robot_paths:
            original_paths.append([list(pt) for pt in path_pts])
            blend_radius_mm   = _safe_float(settings.get("blend_radius_mm"),        0.0)
            pre_smooth_max_deviation_mm = _safe_float(settings.get("pre_smooth_max_deviation_mm"), 1.0)
            adaptive_spacing, spline_multiplier = _derive_interpolation_from_blend_radius(
                blend_radius_mm,
            )
            vel               = _safe_float(settings.get("velocity"),              60.0)
            acc               = _safe_float(settings.get("acceleration"),          30.0)

            pre_smoothed, linear, spline = interpolate_path_two_stage(
                path_pts,
                adaptive_spacing_mm=adaptive_spacing,
                spline_density_multiplier=spline_multiplier,
                return_pre_smoothed=True,
                blend_radius_mm=blend_radius_mm,
                pre_smooth_max_deviation_mm=pre_smooth_max_deviation_mm,
            )
            execution_spacing_mm = max(6.0, adaptive_spacing * 0.75)
            execution_spline = _resample_execution_path(spline, target_spacing_mm=execution_spacing_mm)
            total_spline_pts += len(execution_spline)
            pre_smoothed_paths.append([list(pt) for pt in pre_smoothed])
            linear_paths.append([list(pt) for pt in linear])
            preview_paths.append([list(pt) for pt in spline])

            _logger.info(
                "[EXECUTE] %s: %d raw → %d pre-smooth → %d linear → %d blended pts → %d execute pts | "
                "blend=%.1fmm pre-smooth-dev=%.2fmm spacing=%.1fmm density=%.1fx exec-spacing=%.1fmm vel=%.0f acc=%.0f",
                pattern_type, len(path_pts), len(pre_smoothed), len(linear), len(spline), len(execution_spline),
                blend_radius_mm, pre_smooth_max_deviation_mm, adaptive_spacing, spline_multiplier, execution_spacing_mm, vel, acc,
            )
            for j, pt in enumerate(execution_spline[:3]):
                _logger.debug("[EXECUTE] %s execute[%d]: %s", pattern_type, j, pt)

            self._last_execution_preview_jobs.append(
                {
                    "path": [list(pt) for pt in spline],
                    "execution_path": [list(pt) for pt in execution_spline],
                    "vel": vel,
                    "acc": acc,
                    "pattern_type": pattern_type,
                }
            )
            _logger.info(
                "[EXECUTE] Prepared %d preview waypoints and %d execution waypoints (vel=%.0f acc=%.0f)",
                len(spline), len(execution_spline), vel, acc,
            )

        self._last_interpolation_preview_contours = []
        self._last_interpolation_preview_paths = preview_paths
        self._last_original_preview_paths = original_paths
        self._last_pre_smoothed_preview_paths = pre_smoothed_paths
        self._last_linear_preview_paths = linear_paths
        self._write_debug_path_dump(
            original_paths=original_paths,
            pre_smoothed_paths=pre_smoothed_paths,
            linear_paths=linear_paths,
            preview_paths=preview_paths,
            execution_paths=[
                [list(pt) for pt in (job.get("execution_path") or job.get("path") or [])]
                for job in self._last_execution_preview_jobs
            ],
        )
        _logger.info("[EXECUTE] Done — %d path(s), %d total spline waypoints",
                     len(robot_paths), total_spline_pts)
        return True, f"Previewed: {len(robot_paths)} path(s), {total_spline_pts} interpolated waypoints"

    def get_last_interpolation_preview_contours(self) -> list:
        return list(self._last_interpolation_preview_contours)

    def get_last_interpolation_preview_paths(self) -> list:
        return [
            [list(pt) for pt in path]
            for path in self._last_interpolation_preview_paths
        ]

    def get_last_original_preview_paths(self) -> list:
        return [
            [list(pt) for pt in path]
            for path in self._last_original_preview_paths
        ]

    def get_last_pre_smoothed_preview_paths(self) -> list:
        return [
            [list(pt) for pt in path]
            for path in self._last_pre_smoothed_preview_paths
        ]

    def get_last_linear_preview_paths(self) -> list:
        return [
            [list(pt) for pt in path]
            for path in self._last_linear_preview_paths
        ]

    def get_last_execution_preview_paths(self) -> list:
        return [
            [list(pt) for pt in (job.get("execution_path") or job.get("path") or [])]
            for job in self._last_execution_preview_jobs
        ]

    def get_last_pivot_preview_paths(self) -> tuple[list[list[list[float]]], list[float] | None]:
        if self._path_executor is None:
            return [], None
        return self._path_executor.get_pivot_preview_paths(self._last_execution_preview_jobs)

    def get_last_pivot_motion_preview(self):
        if self._path_executor is None:
            return [], None
        return self._path_executor.get_pivot_motion_preview(self._last_execution_preview_jobs)

    def get_available_execution_modes(self) -> tuple[str, ...]:
        if self._path_executor is not None:
            return tuple(self._path_executor.get_supported_execution_modes())
        return ("continuous", "pose_path", "segmented")

    def can_execute_pickup_to_pivot(self) -> bool:
        if self._path_executor is None:
            return False
        return bool(self._path_executor.supports_pickup_to_pivot())

    def execute_pickup_to_pivot(self) -> tuple[bool, str]:
        if not self._last_execution_preview_jobs:
            return False, "No previewed paths available"
        if self._path_executor is None or not self._path_executor.supports_pickup_to_pivot():
            return False, "Pickup-to-pivot is not supported"
        return self._path_executor.execute_pickup_to_pivot(self._last_execution_preview_jobs)

    def execute_pickup_and_pivot_paint(self) -> tuple[bool, str]:
        if not self._last_execution_preview_jobs:
            return False, "No previewed paths available"
        if self._path_executor is None or not self._path_executor.supports_pickup_to_pivot():
            return False, "Pickup-and-pivot-paint is not supported"
        return self._path_executor.execute_pickup_and_pivot_paint(self._last_execution_preview_jobs)

    def execute_last_preview_paths(self, mode: str = "continuous") -> tuple[bool, str]:
        if not self._last_execution_preview_jobs:
            return False, "No previewed paths available to execute"
        if self._robot_service is None:
            return False, "Robot service is not available"

        if self._path_executor is not None:
            return self._path_executor.execute_preview_paths(
                self._last_execution_preview_jobs,
                mode=mode,
            )

        mode = str(mode or "continuous").strip().lower()
        if mode not in {"continuous", "pose_path", "segmented"}:
            return False, f"Unsupported execution mode: {mode}"

        total_waypoints = 0
        for job in self._last_execution_preview_jobs:
            spline = job.get("execution_path") or job.get("path") or []
            vel = float(job.get("vel", 60.0))
            acc = float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))
            if not spline:
                continue

            if mode == "continuous":
                result = self._robot_service.execute_trajectory(
                    spline, vel=vel, acc=acc, blocking=True)
                if result not in (0, True, None):
                    return False, f"{pattern_type} trajectory execution failed with code {result}"
            elif mode == "pose_path":
                result = self._robot_service.execute_trajectory(
                    spline,
                    vel=vel,
                    acc=acc,
                    blocking=True,
                    orientation_mode="per_waypoint",
                )
                if result not in (0, True, None):
                    return False, f"{pattern_type} pose-path execution failed with code {result}"
            else:
                result = self._execute_segmented_preview_path(spline, vel=vel, acc=acc)
                if not result:
                    return False, f"{pattern_type} segmented execution failed"
            total_waypoints += len(spline)
            _logger.info(
                "[EXECUTE] [RUN FROM PREVIEW] Sent %d waypoints to robot in %s mode (vel=%.0f acc=%.0f)",
                len(spline), mode, vel, acc,
            )

        return True, (
            f"Executed {len(self._last_execution_preview_jobs)} path(s), "
            f"{total_waypoints} waypoints in {mode} mode"
        )

    def _execute_segmented_preview_path(
        self,
        path: list[list[float]],
        vel: float,
        acc: float,
    ) -> bool:
        """Execute the already-interpolated path point-by-point.

        This preserves the current smoothing/interpolation output while avoiding
        the shared continuous execute_path backend, making it easier to inspect
        how the robot behaves at corners and orientation changes.
        """
        if len(path) < 2:
            return True

        for waypoint in path[1:]:
            if len(waypoint) < 6:
                _logger.error("[EXECUTE] Segmented mode requires 6D waypoints, got: %s", waypoint)
                return False
            ok = self._robot_service.move_linear(
                position=list(waypoint[:6]),
                tool=0,
                user=0,
                velocity=vel,
                acceleration=acc,
                blendR=0.0,
                wait_to_reach=True,
            )
            if not ok:
                _logger.error("[EXECUTE] Segmented move_linear failed at waypoint=%s", waypoint)
                return False
        return True

    def _transform_to_robot(self, pts_px: np.ndarray, settings: dict) -> list:
        """Convert (N, 2) pixel points + segment settings → [[x, y, z, rx_degrees, ry_degrees, rz_degrees], ...]."""
        try:
            _defaults = self._segment_config.schema.get_defaults()
            spray_height = float(str(settings.get("spraying_height", _defaults.get("spraying_height", "0"))).replace(",", ""))
            base_position = self._resolve_base_position()
            base_z = base_position[2] + spray_height if base_position is not None else self._z_min + spray_height
            rz_offset = float(settings.get("rz_angle", _defaults.get("rz_angle", "0")))
        except (ValueError, TypeError):
            raise ValueError("Invalid segment settings: spraying_height and rz_angle must be numbers")
        rx, ry = 180.0, 0.0
        robot_xy_points: list[tuple[float, float]] = []

        if self._resolver is not None:
            from src.engine.robot.targeting import VisionPoseRequest

            target_point = self._resolver.registry.by_name(self._target_point_name)
            seeded_results = [
                self._resolver.resolve(
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
                for px, py in pts_px
            ]
            robot_xy_points = [
                (float(result.final_xy[0]), float(result.final_xy[1]))
                for result in seeded_results
            ]
        else:
            if self._transformer is None or not self._transformer.is_available():
                _logger.warning("[EXECUTE] No calibration transformer — using raw pixel coords")
            for px, py in pts_px:
                if self._transformer is not None and self._transformer.is_available():
                    rx_coord, ry_coord = self._transformer.transform(float(px), float(py))
                else:
                    rx_coord, ry_coord = float(px), float(py)
                robot_xy_points.append((float(rx_coord), float(ry_coord)))

        if self._rz_mode == "path_tangent":
            rz_values = _compute_path_aligned_rz_degrees(robot_xy_points, base_rz_offset_degrees=rz_offset)
        else:
            rz_values = [float(rz_offset) for _ in robot_xy_points]

        if self._resolver is not None:
            # Keep XY geometry fixed once it has been resolved from the image.
            # Per-waypoint RZ is attached afterward so orientation changes do not
            # re-run TCP-offset compensation and warp the contour shape.
            result = [
                [
                    float(seed.final_xy[0]),
                    float(seed.final_xy[1]),
                    float(seed.z),
                    rx,
                    ry,
                    float(rz),
                ]
                for seed, rz in zip(seeded_results, rz_values)
            ]
        else:
            result = [
                [float(x), float(y), float(base_z), rx, ry, float(rz)]
                for (x, y), rz in zip(robot_xy_points, rz_values)
            ]
        if result:
            _logger.debug(
                "[EXECUTE] RZ mode=%s first headings=%s",
                self._rz_mode,
                [round(float(point[5]), 3) for point in result[: min(5, len(result))]],
            )
        return result

    def _resolve_base_position(self) -> Optional[list[float]]:
        executor = self._path_executor
        if executor is not None and hasattr(executor, "_resolve_base_position"):
            try:
                position = executor._resolve_base_position()
            except Exception:
                _logger.debug("WorkpieceEditorService: path executor base position lookup failed", exc_info=True)
                position = None
            if position is not None:
                return list(position)
        return None

    def _write_debug_path_dump(
        self,
        *,
        original_paths: list[list[list[float]]],
        pre_smoothed_paths: list[list[list[float]]],
        linear_paths: list[list[list[float]]],
        preview_paths: list[list[list[float]]],
        execution_paths: list[list[list[float]]],
    ) -> None:
        if not self._debug_dump_dir:
            return

        try:
            os.makedirs(self._debug_dump_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(self._debug_dump_dir, f"trajectory_points_{timestamp}.txt")
            sections = [
                ("ORIGINAL", original_paths),
                ("PRE_SMOOTHED", pre_smoothed_paths),
                ("LINEAR", linear_paths),
                ("SPLINE", preview_paths),
                ("EXECUTION", execution_paths),
            ]
            with open(filepath, "w", encoding="utf-8") as handle:
                handle.write(f"# Trajectory point dump\n# timestamp={timestamp}\n# rz_mode={self._rz_mode}\n")
                for section_name, paths in sections:
                    handle.write(f"\n[{section_name}]\n")
                    for path_index, path in enumerate(paths, start=1):
                        handle.write(f"path {path_index} count={len(path)}\n")
                        for point_index, point in enumerate(path):
                            coords = ", ".join(f"{float(value):.6f}" for value in point)
                            handle.write(f"  {point_index:04d}: [{coords}]\n")
            _logger.info("[EXECUTE] Wrote trajectory debug dump to %s", filepath)
        except Exception:
            _logger.debug("[EXECUTE] Failed to write trajectory debug dump", exc_info=True)

    def _build_preview_contours(self, spline_points: list[list[float]]) -> list[np.ndarray]:
        if self._transformer is None or not self._transformer.is_available():
            return []

        sampled_points = spline_points
        if len(sampled_points) > _MAX_PREVIEW_CONTOUR_POINTS:
            sample_idx = np.linspace(0, len(sampled_points) - 1, _MAX_PREVIEW_CONTOUR_POINTS, dtype=int)
            sampled_points = [sampled_points[int(i)] for i in sample_idx]

        robot_xy = np.asarray([[float(pt[0]), float(pt[1])] for pt in sampled_points], dtype=np.float32)
        fast_preview_xy = _fast_inverse_preview_points(self._transformer, robot_xy)

        preview_xy: list[list[float]] = []
        if fast_preview_xy is not None and len(fast_preview_xy) == len(sampled_points):
            preview_xy = [[float(px), float(py)] for px, py in fast_preview_xy]
        else:
            for pt in sampled_points:
                try:
                    px, py = self._transformer.inverse_transform(float(pt[0]), float(pt[1]))
                except Exception:
                    continue
                preview_xy.append([float(px), float(py)])

        if len(preview_xy) < 2:
            return []

        contour = np.array(preview_xy, dtype=np.float32).reshape(-1, 1, 2)
        return [contour]

    def _merge(self, form_data: dict, editor_data) -> dict:
        if not isinstance(editor_data, ContourEditorData):
            return dict(form_data)
        segment_defaults = self._segment_config.schema.get_defaults()
        merged    = {**WorkpieceAdapter.to_workpiece_data(editor_data, default_settings=segment_defaults), **form_data}
        combo_key = self._schema().combo_key
        if combo_key:
            val = form_data.get(combo_key) or form_data.get("glue_type") or form_data.get("glueType")
            if val:
                merged[combo_key] = val
        return merged


def _safe_float(value, default: float) -> float:
    try:
        return float(str(value).replace(",", "")) if value is not None else default
    except (ValueError, TypeError):
        return default

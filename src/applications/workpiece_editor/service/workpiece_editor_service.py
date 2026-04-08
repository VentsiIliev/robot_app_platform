import logging
from typing import Callable, Optional, TYPE_CHECKING
import numpy as np

from src.applications.workpiece_editor.editor_core.config import WorkpieceFormSchema
from src.applications.workpiece_editor.editor_core.config.segment_editor_config import SegmentEditorConfig
from src.applications.workpiece_editor.service import IWorkpieceEditorService
from src.applications.workpiece_editor.editor_core.handlers.SaveWorkpieceHandler import SaveWorkpieceHandler
from src.applications.workpiece_editor.editor_core.adapters.workpiece_adapter import WorkpieceAdapter
from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.vision.i_capture_snapshot_service import ICaptureSnapshotService
from contour_editor.persistence.data.editor_data_model import ContourEditorData

if TYPE_CHECKING:
    from src.engine.robot.targeting import VisionTargetResolver

_logger = logging.getLogger(__name__)


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


def _has_valid_contour(contour) -> bool:
    if contour is None:
        return False
    if isinstance(contour, np.ndarray):
        return int(contour.size) >= 3
    if isinstance(contour, list):
        return len(contour) >= 3
    return False


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
                 robot_service=None,
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
        self._robot_service      = robot_service
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
        preview_contours: list[np.ndarray] = []
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
            total_spline_pts += len(spline)
            pre_smoothed_paths.append([list(pt) for pt in pre_smoothed])
            linear_paths.append([list(pt) for pt in linear])
            preview_paths.append([list(pt) for pt in spline])

            _logger.info(
                "[EXECUTE] %s: %d raw → %d pre-smooth → %d linear → %d blended pts | "
                "blend=%.1fmm pre-smooth-dev=%.2fmm spacing=%.1fmm density=%.1fx vel=%.0f acc=%.0f",
                pattern_type, len(path_pts), len(pre_smoothed), len(linear), len(spline),
                blend_radius_mm, pre_smooth_max_deviation_mm, adaptive_spacing, spline_multiplier, vel, acc,
            )
            for j, pt in enumerate(spline[:3]):
                _logger.debug("[EXECUTE] %s spline[%d]: %s", pattern_type, j, pt)

            preview_contours.extend(self._build_preview_contours(spline))
            self._last_execution_preview_jobs.append(
                {
                    "path": [list(pt) for pt in spline],
                    "vel": vel,
                    "acc": acc,
                    "pattern_type": pattern_type,
                }
            )
            _logger.info(
                "[EXECUTE] [PREVIEW ONLY] Prepared %d interpolated waypoints (vel=%.0f acc=%.0f)",
                len(spline), vel, acc,
            )

        self._last_interpolation_preview_contours = preview_contours
        self._last_interpolation_preview_paths = preview_paths
        self._last_original_preview_paths = original_paths
        self._last_pre_smoothed_preview_paths = pre_smoothed_paths
        self._last_linear_preview_paths = linear_paths
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
            [list(pt) for pt in (job.get("path") or [])]
            for job in self._last_execution_preview_jobs
        ]

    def execute_last_preview_paths(self) -> tuple[bool, str]:
        if not self._last_execution_preview_jobs:
            return False, "No previewed paths available to execute"
        if self._robot_service is None:
            return False, "Robot service is not available"

        total_waypoints = 0
        for job in self._last_execution_preview_jobs:
            spline = job.get("path") or []
            vel = float(job.get("vel", 60.0))
            acc = float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))
            if not spline:
                continue

            result = self._robot_service.execute_trajectory(spline, vel=vel, acc=acc, blocking=True)
            if result not in (0, True, None):
                return False, f"{pattern_type} trajectory execution failed with code {result}"
            total_waypoints += len(spline)
            _logger.info(
                "[EXECUTE] [RUN FROM PREVIEW] Sent %d waypoints to robot (vel=%.0f acc=%.0f)",
                len(spline), vel, acc,
            )

        return True, f"Executed {len(self._last_execution_preview_jobs)} path(s), {total_waypoints} waypoints"

    def _transform_to_robot(self, pts_px: np.ndarray, settings: dict) -> list:
        """Convert (N, 2) pixel points + segment settings → [[x, y, z, rx_degrees, ry_degrees, rz_degrees], ...]."""
        try:
            _defaults = self._segment_config.schema.get_defaults()
            spray_height = float(str(settings.get("spraying_height", _defaults.get("spraying_height", "0"))).replace(",", ""))
            base_z = self._z_min + spray_height
            rz = float(settings.get("rz_angle", _defaults.get("rz_angle", "0")))
        except (ValueError, TypeError):
            base_z, rz = 0.0, 0.0
        rx, ry = 180.0, 0.0

        if self._resolver is not None:
            from src.engine.robot.targeting import VisionPoseRequest
            result = []
            for px, py in pts_px:
                tr = self._resolver.resolve(
                    VisionPoseRequest(float(px), float(py), z_mm=base_z, rz_degrees=rz, rx_degrees=rx, ry_degrees=ry),
                    self._resolver.registry.by_name(self._target_point_name),
                )
                result.append(list(tr.robot_pose()))
            return result

        if self._transformer is None or not self._transformer.is_available():
            _logger.warning("[EXECUTE] No calibration transformer — using raw pixel coords")

        result = []
        for px, py in pts_px:
            if self._transformer is not None and self._transformer.is_available():
                rx_coord, ry_coord = self._transformer.transform(float(px), float(py))
            else:
                rx_coord, ry_coord = float(px), float(py)
            result.append([rx_coord, ry_coord, base_z, rx, ry, rz])
        return result

    def _build_preview_contours(self, spline_points: list[list[float]]) -> list[np.ndarray]:
        if self._transformer is None or not self._transformer.is_available():
            return []

        preview_xy: list[list[float]] = []
        for pt in spline_points:
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

import logging
import os
from dataclasses import dataclass
from typing import Callable, Optional
from datetime import datetime

import numpy as np

from src.applications.workpiece_editor.editor_core.config import WorkpieceFormSchema
from src.applications.workpiece_editor.editor_core.config.segment_editor_config import SegmentEditorConfig
from src.applications.workpiece_editor.service import IWorkpieceEditorService
from src.applications.workpiece_editor.editor_core.handlers.SaveWorkpieceHandler import SaveWorkpieceHandler
from src.applications.workpiece_editor.editor_core.adapters.workpiece_adapter import WorkpieceAdapter
from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.robot.path_preparation import (
    IWorkpiecePathPreparationService,
    WorkpieceExecutionPlan,
)
from src.engine.robot.path_preparation.geometry import (
    fast_inverse_preview_points,
    has_valid_contour,
)
from src.engine.vision.i_capture_snapshot_service import ICaptureSnapshotService
from src.applications.workpiece_editor.service.i_workpiece_path_executor import IWorkpiecePathExecutor
from src.robot_systems.glue.domain.matching.i_matching_service import IMatchingService
from src.robot_systems.paint.processes.paint.dxf_image_placement import map_raw_workpiece_mm_to_image
from contour_editor.persistence.data.editor_data_model import ContourEditorData

_logger = logging.getLogger(__name__)
_MAX_PREVIEW_CONTOUR_POINTS = 180
_DEFAULT_WORKPIECE_HEIGHT_MM = 0.0


@dataclass(frozen=True)
class WorkpieceEditorStorage:
    save_fn: Callable[[dict], tuple[bool, str]]
    update_fn: Callable[[str, dict], tuple[bool, str]]
    id_exists_fn: Optional[Callable[[str], bool]] = None


@dataclass(frozen=True)
class WorkpieceEditorServices:
    vision_service: object = None
    capture_snapshot_service: Optional[ICaptureSnapshotService] = None
    robot_service: object = None
    transformer: Optional[ICoordinateTransformer] = None
    path_executor: Optional[IWorkpiecePathExecutor] = None
    path_preparation_service: Optional[IWorkpiecePathPreparationService] = None
    matching_service: Optional[IMatchingService] = None


@dataclass(frozen=True)
class WorkpieceEditorOptions:
    debug_dump_dir: Optional[str] = None
    enable_dxf_import_test: bool = False


class WorkpieceEditorService(IWorkpieceEditorService):

    def __init__(
        self,
        *,
        storage: WorkpieceEditorStorage,
        services: WorkpieceEditorServices,
        form_schema: WorkpieceFormSchema,
        segment_config: SegmentEditorConfig,
        options: WorkpieceEditorOptions | None = None,
    ):
        options = options or WorkpieceEditorOptions()
        self._vision = services.vision_service
        self._capture_snapshot_service = services.capture_snapshot_service
        self._save_fn = storage.save_fn
        self._update_fn = storage.update_fn
        self._id_exists_fn = storage.id_exists_fn
        self._form_schema = form_schema
        self._segment_config = segment_config
        self._transformer = services.transformer
        self._debug_dump_dir = options.debug_dump_dir
        self._robot_service = services.robot_service
        self._path_executor = services.path_executor
        self._path_preparation_service = services.path_preparation_service
        self._enable_dxf_import_test = bool(options.enable_dxf_import_test)
        self._matching_service = services.matching_service
        self._editing_storage_id = None
        self._last_execution_plan: WorkpieceExecutionPlan | None = None

    def set_editing(self, storage_id) -> None:
        self._editing_storage_id = storage_id
        _logger.debug("WorkpieceEditorService: editing_storage_id=%s", storage_id)

    def _schema(self) -> WorkpieceFormSchema:
        return self._form_schema() if callable(self._form_schema) else self._form_schema

    def get_form_schema(self) -> WorkpieceFormSchema:
        return self._schema()

    def get_segment_config(self) -> SegmentEditorConfig:
        return self._segment_config

    def can_import_dxf_test(self) -> bool:
        return self._enable_dxf_import_test

    def can_match_saved_workpieces(self) -> bool:
        return bool(self._matching_service is not None and self._matching_service.can_match_saved_workpieces())

    def match_saved_workpieces(self, contour) -> tuple[bool, dict | None, str]:
        if self._matching_service is None:
            return False, None, "Matching is not available in this editor."
        return self._matching_service.match_saved_workpieces(contour)

    def prepare_dxf_test_raw_for_image(
        self,
        raw: dict,
        image_width: float,
        image_height: float,
    ) -> dict:
        placed = map_raw_workpiece_mm_to_image(
            raw,
            float(image_width),
            float(image_height),
            self._transformer,
        )
        _logger.info(
            "Prepared DXF test workpiece for image placement: image=(%.1f, %.1f)",
            float(image_width),
            float(image_height),
        )
        return placed

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
            complete    = self._normalize_workpiece_metadata(complete)
            required    = self._schema().get_required_keys()
            is_valid, errors = SaveWorkpieceHandler.validate_form_data(complete, required)
            if not is_valid:
                return False, f"Validation failed: {', '.join(errors)}"

            if not has_valid_contour(complete.get("contour")):
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
        self._last_execution_plan = None
        form_data   = data.get("form_data", data)
        editor_data = data.get("editor_data")
        merged      = self._merge(form_data, editor_data) if editor_data else dict(form_data)
        if self._path_preparation_service is None:
            return False, "Path preparation service is not available"
        try:
            execution_plan = self._path_preparation_service.build_execution_plan(merged)
        except Exception as exc:
            _logger.exception("[EXECUTE] Failed to build preview package")
            return False, str(exc)

        self._last_execution_plan = execution_plan
        self._write_debug_path_dump(
            raw_paths=execution_plan.raw_paths,
            prepared_paths=execution_plan.prepared_paths,
            curve_paths=execution_plan.curve_paths,
            sampled_paths=execution_plan.sampled_paths,
            execution_paths=execution_plan.execution_paths(),
        )
        _logger.info("[EXECUTE] Done — %d path(s), %d total spline waypoints",
                     len(execution_plan.execution_jobs), execution_plan.total_spline_pts)
        return True, f"Previewed: {len(execution_plan.execution_jobs)} path(s), {execution_plan.total_spline_pts} interpolated waypoints"

    @staticmethod
    def _clone_paths(paths: list[list[list[float]]]) -> list[list[list[float]]]:
        return [
            [list(pt) for pt in path]
            for path in paths
        ]

    def get_last_sampled_preview_paths(self) -> list:
        if self._last_execution_plan is None:
            return []
        return self._clone_paths(self._last_execution_plan.sampled_paths)

    def get_last_raw_preview_paths(self) -> list:
        if self._last_execution_plan is None:
            return []
        return self._clone_paths(self._last_execution_plan.raw_paths)

    def get_last_prepared_preview_paths(self) -> list:
        if self._last_execution_plan is None:
            return []
        return self._clone_paths(self._last_execution_plan.prepared_paths)

    def get_last_curve_preview_paths(self) -> list:
        if self._last_execution_plan is None:
            return []
        return self._clone_paths(self._last_execution_plan.curve_paths)

    def get_last_execution_preview_paths(self) -> list:
        if self._last_execution_plan is None:
            return []
        return self._last_execution_plan.execution_paths()

    def get_last_pivot_preview_paths(self) -> tuple[list[list[list[float]]], list[float] | None]:
        if self._path_executor is None:
            return [], None
        if self._last_execution_plan is None:
            return [], None
        return self._path_executor.get_pivot_preview_paths(self._last_execution_plan)

    def get_last_pivot_motion_preview(self):
        if self._path_executor is None:
            return [], None
        if self._last_execution_plan is None:
            return [], None
        return self._path_executor.get_pivot_motion_preview(self._last_execution_plan)

    def get_available_execution_modes(self) -> tuple[str, ...]:
        if self._path_executor is not None:
            return tuple(self._path_executor.get_supported_execution_modes())
        return ("continuous", "pose_path", "segmented")

    def can_execute_pickup_to_pivot(self) -> bool:
        if self._path_executor is None:
            return False
        return bool(self._path_executor.supports_pickup_to_pivot())

    def execute_pickup_to_pivot(self) -> tuple[bool, str]:
        if self._last_execution_plan is None:
            return False, "No previewed paths available"
        if self._path_executor is None or not self._path_executor.supports_pickup_to_pivot():
            return False, "Pickup-to-pivot is not supported"
        return self._path_executor.execute_pickup_to_pivot(self._last_execution_plan)

    def execute_pickup_and_pivot_paint(self) -> tuple[bool, str]:
        if self._last_execution_plan is None:
            return False, "No previewed paths available"
        if self._path_executor is None or not self._path_executor.supports_pickup_to_pivot():
            return False, "Pickup-and-pivot-paint is not supported"
        return self._path_executor.execute_pickup_and_pivot_paint(self._last_execution_plan)

    def execute_last_preview_paths(self, mode: str = "continuous") -> tuple[bool, str]:
        if self._last_execution_plan is None:
            return False, "No previewed paths available to execute"
        if self._robot_service is None:
            return False, "Robot service is not available"

        if self._path_executor is not None:
            return self._path_executor.execute_preview_paths(
                self._last_execution_plan,
                mode=mode,
            )

        mode = str(mode or "continuous").strip().lower()
        if mode not in {"continuous", "pose_path", "segmented"}:
            return False, f"Unsupported execution mode: {mode}"

        total_waypoints = 0
        for job in self._last_execution_plan.execution_jobs:
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
            f"Executed {len(self._last_execution_plan.execution_jobs)} path(s), "
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

    def _write_debug_path_dump(
        self,
        *,
        raw_paths: list[list[list[float]]],
        prepared_paths: list[list[list[float]]],
        curve_paths: list[list[list[float]]],
        sampled_paths: list[list[list[float]]],
        execution_paths: list[list[list[float]]],
    ) -> None:
        if not self._debug_dump_dir:
            return

        try:
            os.makedirs(self._debug_dump_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(self._debug_dump_dir, f"trajectory_points_{timestamp}.txt")
            sections = [
                ("RAW", raw_paths),
                ("PREPARED", prepared_paths),
                ("CURVE", curve_paths),
                ("SAMPLED", sampled_paths),
                ("EXECUTION", execution_paths),
            ]
            with open(filepath, "w", encoding="utf-8") as handle:
                handle.write(f"# Trajectory point dump\n# timestamp={timestamp}\n")
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
        fast_preview_xy = fast_inverse_preview_points(self._transformer, robot_xy)

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
            return self._normalize_workpiece_metadata(dict(form_data))
        segment_defaults = self._segment_config.schema.get_defaults()
        merged    = {**WorkpieceAdapter.to_workpiece_data(editor_data, default_settings=segment_defaults), **form_data}
        combo_key = self._schema().combo_key
        if combo_key:
            val = form_data.get(combo_key) or form_data.get("glue_type") or form_data.get("glueType")
            if val:
                merged[combo_key] = val
        return self._normalize_workpiece_metadata(merged)

    @staticmethod
    def _normalize_workpiece_metadata(data: dict) -> dict:
        normalized = dict(data or {})
        normalized["height_mm"] = _safe_float(
            normalized.get("height_mm"),
            _DEFAULT_WORKPIECE_HEIGHT_MM,
        )
        return normalized


def _safe_float(value, default: float) -> float:
    try:
        return float(str(value).replace(",", "")) if value is not None else default
    except (ValueError, TypeError):
        return default

import logging
import os
from typing import Callable, Optional, TYPE_CHECKING
from datetime import datetime
import copy
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
_SEGMENT_PREPROCESS_MIN_SPACING_KEY = "preprocess_min_spacing_mm"
_SEGMENT_INTERPOLATION_SPACING_KEY = "interpolation_spacing_mm"
_SEGMENT_DENSE_SAMPLING_FACTOR_KEY = "dense_sampling_factor"
_SEGMENT_EXECUTION_SPACING_KEY = "execution_spacing_mm"
_SEGMENT_TANGENT_LOOKAHEAD_DISTANCE_KEY = "path_tangent_lookahead_mm"
_SEGMENT_TANGENT_DEADBAND_KEY = "path_tangent_deadband_deg"
_EXECUTION_INTERPOLATION_SPACING_MM = 10.0
_EXECUTION_MIN_PREPROCESS_SPACING_MM = 2.5
_EXECUTION_DENSE_SAMPLING_FACTOR = 0.25
_EXECUTION_OUTPUT_SPACING_SCALE = 0.75
_EXECUTION_MIN_OUTPUT_SPACING_MM = 6.0
_EXECUTION_DEFAULT_OUTPUT_SPACING_MM = max(
    _EXECUTION_MIN_OUTPUT_SPACING_MM,
    _EXECUTION_INTERPOLATION_SPACING_MM * _EXECUTION_OUTPUT_SPACING_SCALE,
)
_PATH_TANGENT_HEADING_SMOOTHING_WINDOW = 5
_PATH_TANGENT_LOOKAHEAD_DISTANCE_MM = 15.0
_PATH_TANGENT_HEADING_DEADBAND_DEG = 5.0
_AUTO_DENSIFY_TRIGGER_RATIO = 2.5
_AUTO_DENSIFY_TARGET_RATIO = 1.25
_DEFAULT_WORKPIECE_HEIGHT_MM = 0.0


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
    return (
        preprocess_spacing_mm,
        interpolation_spacing_mm,
        dense_sampling_factor,
        execution_spacing_mm,
    )


def _resolve_segment_tangent_settings(settings: dict) -> tuple[float, float]:
    lookahead_distance_mm = max(
        1.0,
        _safe_float(settings.get(_SEGMENT_TANGENT_LOOKAHEAD_DISTANCE_KEY), _PATH_TANGENT_LOOKAHEAD_DISTANCE_MM),
    )
    heading_deadband_deg = max(
        0.0,
        _safe_float(settings.get(_SEGMENT_TANGENT_DEADBAND_KEY), _PATH_TANGENT_HEADING_DEADBAND_DEG),
    )
    return lookahead_distance_mm, heading_deadband_deg


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


def _rebuild_pose_path_from_xy(
    xy_points: np.ndarray,
    prototype_path: list[list[float]],
    rz_mode: str,
    tangent_lookahead_distance_mm: float = _PATH_TANGENT_LOOKAHEAD_DISTANCE_MM,
    tangent_heading_deadband_deg: float = _PATH_TANGENT_HEADING_DEADBAND_DEG,
) -> list[list[float]]:
    if len(xy_points) == 0 or not prototype_path:
        return []

    first_pose = prototype_path[0]
    base_z = float(first_pose[2]) if len(first_pose) >= 3 else 0.0
    rx = float(first_pose[3]) if len(first_pose) >= 4 else 180.0
    ry = float(first_pose[4]) if len(first_pose) >= 5 else 0.0
    base_rz = float(first_pose[5]) if len(first_pose) >= 6 else 0.0

    robot_xy_points = [(float(point[0]), float(point[1])) for point in xy_points]
    if str(rz_mode or "constant").strip().lower() == "path_tangent":
        rz_values = _compute_path_aligned_rz_degrees(
            robot_xy_points,
            base_rz_offset_degrees=base_rz,
            lookahead_distance_mm=tangent_lookahead_distance_mm,
            heading_deadband_deg=tangent_heading_deadband_deg,
        )
    else:
        rz_values = [base_rz for _ in robot_xy_points]

    return [
        [float(x), float(y), base_z, rx, ry, float(rz)]
        for (x, y), rz in zip(robot_xy_points, rz_values)
    ]


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
    lookahead_distance_mm: float = _PATH_TANGENT_LOOKAHEAD_DISTANCE_MM,
    heading_deadband_deg: float = _PATH_TANGENT_HEADING_DEADBAND_DEG,
) -> list[float]:
    """Compute per-waypoint RZ from a lookahead turn signal.

    The path heading is smoothed first. Each waypoint then compares the current
    local heading against a heading a short distance ahead along the path. Only
    when that accumulated turn exceeds a deadband does the robot start rotating.
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

    if len(segment_headings) >= 3:
        window = min(_PATH_TANGENT_HEADING_SMOOTHING_WINDOW, len(segment_headings))
        if window % 2 == 0:
            window -= 1
        if window >= 3:
            radius = window // 2
            padded = np.pad(np.asarray(segment_headings, dtype=float), (radius, radius), mode="edge")
            smoothed_headings = []
            for index in range(len(segment_headings)):
                smoothed_headings.append(float(np.mean(padded[index:index + window])))
            segment_headings = smoothed_headings

    point_distances = [0.0]
    for index in range(1, len(robot_xy_points)):
        current = np.asarray(robot_xy_points[index], dtype=float)
        previous = np.asarray(robot_xy_points[index - 1], dtype=float)
        point_distances.append(point_distances[-1] + float(np.linalg.norm(current - previous)))

    lookahead_distance_mm = max(float(lookahead_distance_mm), 1.0)
    lookahead_headings: list[float] = []
    for index in range(len(segment_headings)):
        start_distance = point_distances[index]
        target_distance = start_distance + lookahead_distance_mm
        lookahead_index = index
        while (
            lookahead_index + 1 < len(segment_headings)
            and point_distances[lookahead_index + 1] < target_distance
        ):
            lookahead_index += 1
        lookahead_headings.append(float(segment_headings[lookahead_index]))

    rz_values: list[float] = [float(base_rz_offset_degrees)]
    for index in range(len(robot_xy_points) - 1):
        if index == 0:
            rz_values.append(float(base_rz_offset_degrees))
            continue

        lookahead_turn = float(lookahead_headings[index] - segment_headings[index])
        while lookahead_turn > 180.0:
            lookahead_turn -= 360.0
        while lookahead_turn < -180.0:
            lookahead_turn += 360.0

        if abs(lookahead_turn) < float(heading_deadband_deg):
            lookahead_turn = 0.0

        rz_values.append(float(base_rz_offset_degrees) + lookahead_turn)

    return rz_values[:len(robot_xy_points)]


def _unwrap_degrees(previous: float, current: float) -> float:
    value = float(current)
    prev = float(previous)
    while value - prev > 180.0:
        value -= 360.0
    while value - prev < -180.0:
        value += 360.0
    return value


def _normalize_degrees(angle: float) -> float:
    value = float(angle)
    while value > 180.0:
        value -= 360.0
    while value <= -180.0:
        value += 360.0
    return value


def _compute_pickup_rz_from_robot_path(
    path: list[list[float]],
    pickup_xy: tuple[float, float],
) -> float:
    if len(path) < 2:
        return 0.0

    points = np.asarray([[float(p[0]), float(p[1])] for p in path if len(p) >= 2], dtype=float)
    if len(points) < 2:
        return 0.0

    pickup_vec = np.asarray([float(pickup_xy[0]), float(pickup_xy[1])], dtype=float)
    closest_index = int(np.argmin(np.linalg.norm(points - pickup_vec, axis=1)))

    candidate_pairs: list[tuple[int, int]] = []
    if closest_index > 0:
        candidate_pairs.append((closest_index - 1, closest_index))
    if closest_index + 1 < len(points):
        candidate_pairs.append((closest_index, closest_index + 1))
    if closest_index > 0 and closest_index + 1 < len(points):
        candidate_pairs.append((closest_index - 1, closest_index + 1))

    dx = dy = 0.0
    for start_idx, end_idx in candidate_pairs:
        segment = points[end_idx] - points[start_idx]
        seg_len = float(np.linalg.norm(segment))
        if seg_len > 1e-6:
            dx = float(segment[0])
            dy = float(segment[1])
            break

    if abs(dx) <= 1e-9 and abs(dy) <= 1e-9:
        return 0.0

    heading_from_x_deg = float(np.degrees(np.arctan2(dy, dx)))
    heading_relative_to_y_deg = heading_from_x_deg - 90.0
    return _normalize_degrees(heading_relative_to_y_deg)


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
                 target_point_name: str = "",
                 pickup_target_point_name: str = "",
                 calibration_frame_name: str = "",
                 enable_dxf_import_test: bool = False,
                 execute_from_workpiece_layer: bool = False,
                 list_saved_workpieces_fn: Optional[Callable[[], list[dict]]] = None,
                 load_saved_workpiece_fn: Optional[Callable[[str], Optional[dict]]] = None,
                 run_matching_fn: Optional[Callable[[list, list], tuple]] = None,
                 pixel_height_compensation_fn: Optional[Callable[[float], tuple[float, float]]] = None):
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
        self._enable_dxf_import_test = bool(enable_dxf_import_test)
        self._execute_from_workpiece_layer = bool(execute_from_workpiece_layer)
        self._list_saved_workpieces_fn = list_saved_workpieces_fn
        self._load_saved_workpiece_fn = load_saved_workpiece_fn
        self._run_matching_fn = run_matching_fn
        self._pixel_height_compensation_fn = pixel_height_compensation_fn
        self._editing_storage_id = None
        self._target_point_name  = str(target_point_name or "").strip().lower()
        self._pickup_target_point_name = str(
            pickup_target_point_name or self._target_point_name or ""
        ).strip().lower()
        self._calibration_frame_name = str(calibration_frame_name or "").strip().lower()
        self._last_interpolation_preview_contours: list[np.ndarray] = []
        self._last_sampled_preview_paths: list[list[list[float]]] = []
        self._last_raw_preview_paths: list[list[list[float]]] = []
        self._last_prepared_preview_paths: list[list[list[float]]] = []
        self._last_curve_preview_paths: list[list[list[float]]] = []
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

    def can_import_dxf_test(self) -> bool:
        return self._enable_dxf_import_test

    def can_match_saved_workpieces(self) -> bool:
        return (
            callable(self._list_saved_workpieces_fn)
            and callable(self._load_saved_workpiece_fn)
            and callable(self._run_matching_fn)
        )

    def match_saved_workpieces(self, contour) -> tuple[bool, dict | None, str]:
        if not self.can_match_saved_workpieces():
            return False, None, "Matching is not available in this editor."

        class _MatchableWorkpiece:
            def __init__(self, raw: dict, storage_id: str | None = None):
                self._raw = copy.deepcopy(raw or {})
                self.storage_id = storage_id
                self.workpieceId = self._raw.get("workpieceId", "")
                self.name = self._raw.get("name", "")
                self.contour = copy.deepcopy(self._raw.get("contour", []))
                self.sprayPattern = copy.deepcopy(self._raw.get("sprayPattern", {"Contour": [], "Fill": []}))
                self.pickupPoint = self._raw.get("pickupPoint")

            def get_main_contour(self):
                contour_entry = self.contour
                if isinstance(contour_entry, dict):
                    contour_points = contour_entry.get("contour", [])
                else:
                    contour_points = contour_entry or []
                return np.asarray(contour_points, dtype=np.float32)

            def get_spray_pattern_contours(self):
                return list((self.sprayPattern or {}).get("Contour", []))

            def get_spray_pattern_fills(self):
                return list((self.sprayPattern or {}).get("Fill", []))

            def to_raw(self) -> dict:
                raw = copy.deepcopy(self._raw)
                raw["contour"] = copy.deepcopy(self.contour)
                raw["sprayPattern"] = copy.deepcopy(self.sprayPattern)
                if self.pickupPoint is not None:
                    raw["pickupPoint"] = self.pickupPoint
                return raw

        try:
            stored = self._list_saved_workpieces_fn() or []
            candidates: list[_MatchableWorkpiece] = []
            for item in stored:
                storage_id = item.get("id")
                if not storage_id:
                    continue
                raw = self._load_saved_workpiece_fn(storage_id)
                if not raw or not raw.get("contour"):
                    continue
                candidates.append(_MatchableWorkpiece(raw, storage_id=storage_id))

            if not candidates:
                return False, None, "No saved workpieces available."

            result, no_match_count, matched_contours, unmatched_contours = self._run_matching_fn(
                candidates,
                [contour],
            )
            workpieces = list((result or {}).get("workpieces", []))
            confidences = list((result or {}).get("mlConfidences", []))
            if not workpieces:
                return False, None, f"No match found. Saved workpieces checked: {len(candidates)}"

            best = workpieces[0]
            raw = best.to_raw() if hasattr(best, "to_raw") else None
            if raw is None:
                return False, None, "Matched workpiece could not be converted."
            confidence = None
            if confidences:
                try:
                    confidence = float(confidences[0])
                except Exception:
                    confidence = None
            return True, {
                "raw": raw,
                "storage_id": getattr(best, "storage_id", None),
                "workpieceId": getattr(best, "workpieceId", "") or raw.get("workpieceId", ""),
                "name": getattr(best, "name", "") or raw.get("name", ""),
                "candidate_count": len(candidates),
                "no_match_count": int(no_match_count),
                "confidence": confidence,
            }, "Matched workpiece."
        except Exception as exc:
            _logger.exception("match_saved_workpieces failed")
            return False, None, str(exc)

    def prepare_dxf_test_raw_for_image(
        self,
        raw: dict,
        image_width: float,
        image_height: float,
    ) -> dict:
        placed = copy.deepcopy(raw)
        contour = placed.get("contour") or []
        points = [point[0] for point in contour if point and point[0]]
        if not points:
            return placed

        self._map_raw_workpiece_mm_to_image(placed, float(image_width), float(image_height))
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

    def _estimate_local_image_basis(self, image_width: float, image_height: float) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        transformer = self._transformer
        if transformer is None or not transformer.is_available():
            return None

        center_px = np.array([float(image_width) * 0.5, float(image_height) * 0.5], dtype=float)
        try:
            center_robot = np.asarray(transformer.transform(float(center_px[0]), float(center_px[1])), dtype=float)
            pixel_origin = np.asarray(
                transformer.inverse_transform(float(center_robot[0]), float(center_robot[1])),
                dtype=float,
            )
            pixel_x = np.asarray(
                transformer.inverse_transform(float(center_robot[0] + 1.0), float(center_robot[1])),
                dtype=float,
            )
            pixel_y = np.asarray(
                transformer.inverse_transform(float(center_robot[0]), float(center_robot[1] + 1.0)),
                dtype=float,
            )
            basis_x = pixel_x - pixel_origin
            basis_y = pixel_y - pixel_origin
            if float(np.linalg.norm(basis_x)) > 1e-6 and float(np.linalg.norm(basis_y)) > 1e-6:
                return pixel_origin, basis_x, basis_y
        except Exception:
            _logger.debug("Failed to estimate local image basis from transformer", exc_info=True)
        return None

    def _map_raw_workpiece_mm_to_image(self, raw: dict, image_width: float, image_height: float) -> None:
        contour = raw.get("contour") or []
        points = [point[0] for point in contour if point and point[0]]
        if not points:
            return

        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        contour_center_mm = np.array([0.5 * (min(xs) + max(xs)), 0.5 * (min(ys) + max(ys))], dtype=float)

        image_center = np.array([float(image_width) * 0.5, float(image_height) * 0.5], dtype=float)
        basis = self._estimate_local_image_basis(float(image_width), float(image_height))
        if basis is None:
            pixel_origin = image_center
            basis_x = np.array([1.0, 0.0], dtype=float)
            basis_y = np.array([0.0, 1.0], dtype=float)
        else:
            pixel_origin, basis_x, basis_y = basis

        def _map_contour(contour_array):
            for point in contour_array or []:
                if point and point[0]:
                    local_mm = np.array(
                        [
                            float(point[0][0]) - float(contour_center_mm[0]),
                            float(point[0][1]) - float(contour_center_mm[1]),
                        ],
                        dtype=float,
                    )
                    mapped = image_center + local_mm[0] * basis_x + local_mm[1] * basis_y
                    point[0][0] = float(mapped[0])
                    point[0][1] = float(mapped[1])

        _map_contour(raw.get("contour"))
        spray = raw.get("sprayPattern") or {}
        for key in ("Contour", "Fill"):
            for segment in spray.get(key, []):
                _map_contour(segment.get("contour"))

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
        from src.engine.robot.path_interpolation.new_interpolation.interpolation_pipeline import (
            ContourPathPipeline,
            InterpolationConfig,
            PreprocessConfig,
            RuckigConfig,
        )

        self._last_interpolation_preview_contours = []
        self._last_sampled_preview_paths = []
        self._last_raw_preview_paths = []
        self._last_prepared_preview_paths = []
        self._last_curve_preview_paths = []
        self._last_execution_preview_jobs = []
        form_data   = data.get("form_data", data)
        editor_data = data.get("editor_data")
        merged      = self._merge(form_data, editor_data) if editor_data else dict(form_data)

        spray_pattern = merged.get("sprayPattern", {})
        workpiece_height_mm = _safe_float(merged.get("height_mm"), _DEFAULT_WORKPIECE_HEIGHT_MM)
        use_workpiece_layer = False
        if not spray_pattern or not any(spray_pattern.get(k) for k in ("Contour", "Fill")):
            if self._execute_from_workpiece_layer and _has_valid_contour(merged.get("contour")):
                use_workpiece_layer = True
                _logger.info("[EXECUTE] No spray patterns found; using workpiece layer for execution")
            else:
                _logger.warning("[EXECUTE] No spray patterns in workpiece data")
                return False, "No spray patterns found — draw Contour or Fill paths first"

        robot_paths = []
        pickup_px = self._extract_pickup_pixel(merged)
        pickup_xy = None
        pickup_rz = 0.0
        pickup_camera_xy = None

        if use_workpiece_layer:
            contour_arr = merged.get("contour", [])
            settings = {
                key: value
                for key, value in merged.items()
                if key not in {"contour", "sprayPattern"}
            }
            settings["height_mm"] = workpiece_height_mm
            if not isinstance(contour_arr, np.ndarray):
                contour_arr = np.array(contour_arr, dtype=np.float32)
            if contour_arr.size != 0:
                pts_px = contour_arr.reshape(-1, 2)
                _logger.info("[EXECUTE] Workpiece: %d pixel points | settings=%s", len(pts_px), settings)
                robot_pts = self._transform_to_robot(pts_px, settings)
                if robot_pts:
                    robot_paths.append((robot_pts, settings, "Workpiece"))
                else:
                    _logger.warning("[EXECUTE] Workpiece: no robot points after transform")
        else:
            for pattern_type in ("Contour", "Fill"):
                patterns = spray_pattern.get(pattern_type, [])
                if not patterns:
                    continue
                _logger.info("[EXECUTE] %d %s pattern(s)", len(patterns), pattern_type)

                for i, pattern in enumerate(patterns):
                    contour_arr = pattern.get("contour", [])
                    settings    = dict(pattern.get("settings", {}) or {})
                    settings["height_mm"] = workpiece_height_mm

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
        sampled_paths: list[list[list[float]]] = []
        raw_paths: list[list[list[float]]] = []
        prepared_paths: list[list[list[float]]] = []
        curve_paths: list[list[list[float]]] = []
        for path_pts, settings, pattern_type in robot_paths:
            raw_paths.append([list(pt) for pt in path_pts])
            vel               = _safe_float(settings.get("velocity"),              60.0)
            acc               = _safe_float(settings.get("acceleration"),          30.0)
            (
                preprocess_spacing_mm,
                interpolation_spacing_mm,
                dense_sampling_factor,
                execution_spacing_mm,
            ) = _resolve_segment_interpolation_settings(settings)
            tangent_lookahead_distance_mm, tangent_heading_deadband_deg = _resolve_segment_tangent_settings(settings)
            input_densify_spacing_mm = _auto_input_densify_spacing(
                path_pts,
                interpolation_spacing_mm,
            )

            pipeline = ContourPathPipeline(
                preprocess=PreprocessConfig(
                    min_spacing=preprocess_spacing_mm,
                    max_segment_length=input_densify_spacing_mm,
                    noise_method="none",
                    noise_strength=0.0,
                ),
                interpolation=InterpolationConfig(
                    method="pchip",
                    output_spacing=interpolation_spacing_mm,
                    dense_sampling_factor=dense_sampling_factor,
                ),
                ruckig=RuckigConfig(
                    enabled=False,
                ),
            )
            pipeline_result = pipeline.run(np.asarray(path_pts, dtype=float)[:, :2])

            prepared_path = _rebuild_pose_path_from_xy(
                pipeline_result.prepared,
                path_pts,
                self._rz_mode,
                tangent_lookahead_distance_mm=tangent_lookahead_distance_mm,
                tangent_heading_deadband_deg=tangent_heading_deadband_deg,
            )
            curve_path = _rebuild_pose_path_from_xy(
                pipeline_result.curve,
                path_pts,
                self._rz_mode,
                tangent_lookahead_distance_mm=tangent_lookahead_distance_mm,
                tangent_heading_deadband_deg=tangent_heading_deadband_deg,
            )
            sampled_path = _rebuild_pose_path_from_xy(
                pipeline_result.sampled,
                path_pts,
                self._rz_mode,
                tangent_lookahead_distance_mm=tangent_lookahead_distance_mm,
                tangent_heading_deadband_deg=tangent_heading_deadband_deg,
            )

            execution_spline = _resample_execution_path(sampled_path, target_spacing_mm=execution_spacing_mm)
            total_spline_pts += len(execution_spline)
            prepared_paths.append([list(pt) for pt in prepared_path])
            curve_paths.append([list(pt) for pt in curve_path])
            sampled_paths.append([list(pt) for pt in sampled_path])

            _logger.info(
                "[EXECUTE] %s: %d raw → %d prepared → %d curve → %d sampled pts → %d execute pts | "
                "pipeline=pchip filter=none ruckig=off preprocess-spacing=%.1fmm auto-input-densify=%.1fmm sampled-spacing=%.1fmm dense-factor=%.2f exec-spacing=%.1fmm vel=%.0f acc=%.0f",
                pattern_type, len(path_pts), len(prepared_path), len(curve_path), len(sampled_path), len(execution_spline),
                preprocess_spacing_mm,
                input_densify_spacing_mm,
                interpolation_spacing_mm,
                dense_sampling_factor,
                execution_spacing_mm,
                vel,
                acc,
            )

            for j, pt in enumerate(execution_spline[:3]):
                _logger.debug("[EXECUTE] %s execute[%d]: %s", pattern_type, j, pt)

            if pickup_px is not None and pickup_xy is None:
                try:
                    pickup_camera_xy = self._transform_single_pixel_to_robot(
                        float(pickup_px[0]),
                        float(pickup_px[1]),
                        {
                            "height_mm": workpiece_height_mm,
                            **merged,
                        },
                        target_point_name=self._target_point_name,
                        frame_name=self._calibration_frame_name,
                        rz_override=0.0,
                    )
                    pickup_rz = _compute_pickup_rz_from_robot_path(
                        execution_spline,
                        pickup_camera_xy,
                    )
                    pickup_xy = self._transform_single_pixel_to_robot(
                        float(pickup_px[0]),
                        float(pickup_px[1]),
                        {
                            "height_mm": workpiece_height_mm,
                            **merged,
                        },
                        target_point_name=self._pickup_target_point_name,
                        frame_name=self._calibration_frame_name,
                        rz_override=pickup_rz,
                    )
                    _logger.info(
                        "[EXECUTE] Resolved pickup target: pixel=(%.3f, %.3f) camera_xy=(%.3f, %.3f) pickup_rz=%.3f pickup_xy=(%.3f, %.3f)",
                        float(pickup_px[0]),
                        float(pickup_px[1]),
                        float(pickup_camera_xy[0]),
                        float(pickup_camera_xy[1]),
                        float(pickup_rz),
                        float(pickup_xy[0]),
                        float(pickup_xy[1]),
                    )
                except Exception:
                    _logger.exception("[EXECUTE] Failed to resolve pickup point to robot XY")
                    pickup_xy = None
                    pickup_rz = 0.0

            self._last_execution_preview_jobs.append(
                {
                    "path": [list(pt) for pt in sampled_path],
                    "execution_path": [list(pt) for pt in execution_spline],
                    "vel": vel,
                    "acc": acc,
                    "pattern_type": pattern_type,
                    "pickup_xy": [float(pickup_xy[0]), float(pickup_xy[1])] if pickup_xy is not None else None,
                    "pickup_rz": float(pickup_rz),
                    "pickup_target_point_name": str(self._pickup_target_point_name or "").strip().lower(),
                }
            )

            _logger.info(
                "[EXECUTE] Prepared %d preview waypoints and %d execution waypoints (vel=%.0f acc=%.0f)",
                len(sampled_path), len(execution_spline), vel, acc,
            )

        self._last_interpolation_preview_contours = []
        self._last_sampled_preview_paths = sampled_paths
        self._last_raw_preview_paths = raw_paths
        self._last_prepared_preview_paths = prepared_paths
        self._last_curve_preview_paths = curve_paths
        self._write_debug_path_dump(
            raw_paths=raw_paths,
            prepared_paths=prepared_paths,
            curve_paths=curve_paths,
            sampled_paths=sampled_paths,
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

    def get_last_sampled_preview_paths(self) -> list:
        return [
            [list(pt) for pt in path]
            for path in self._last_sampled_preview_paths
        ]

    def get_last_raw_preview_paths(self) -> list:
        return [
            [list(pt) for pt in path]
            for path in self._last_raw_preview_paths
        ]

    def get_last_prepared_preview_paths(self) -> list:
        return [
            [list(pt) for pt in path]
            for path in self._last_prepared_preview_paths
        ]

    def get_last_curve_preview_paths(self) -> list:
        return [
            [list(pt) for pt in path]
            for path in self._last_curve_preview_paths
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
            workpiece_height_mm = _safe_float(settings.get("height_mm"), _DEFAULT_WORKPIECE_HEIGHT_MM)
        except (ValueError, TypeError):
            raise ValueError("Invalid segment settings: spraying_height and rz_angle must be numbers")
        rx, ry = 180.0, 0.0
        robot_xy_points: list[tuple[float, float]] = []
        compensated_pts_px = np.asarray(pts_px, dtype=np.float64).copy()

        compensation_dx_px = 0.0
        compensation_dy_px = 0.0
        if callable(self._pixel_height_compensation_fn) and abs(workpiece_height_mm) > 1e-9:
            try:
                compensation_dx_px, compensation_dy_px = self._pixel_height_compensation_fn(workpiece_height_mm)
                compensated_pts_px[:, 0] = compensated_pts_px[:, 0] - float(compensation_dx_px)
                compensated_pts_px[:, 1] = compensated_pts_px[:, 1] - float(compensation_dy_px)
                _logger.info(
                    "[EXECUTE] Applied pixel height compensation: height_mm=%.3f pixel_delta=(%.6f, %.6f)",
                    workpiece_height_mm,
                    float(compensation_dx_px),
                    float(compensation_dy_px),
                )
            except Exception:
                _logger.exception("[EXECUTE] Failed to apply pixel height compensation")

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
                for px, py in compensated_pts_px
            ]
            robot_xy_points = [
                (float(result.final_xy[0]), float(result.final_xy[1]))
                for result in seeded_results
            ]
        else:
            if self._transformer is None or not self._transformer.is_available():
                _logger.warning("[EXECUTE] No calibration transformer — using raw pixel coords")
            for px, py in compensated_pts_px:
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
                    float(x),
                    float(y),
                    float(seed.z),
                    rx,
                    ry,
                    float(rz),
                ]
                for seed, (x, y), rz in zip(seeded_results, robot_xy_points, rz_values)
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
            _defaults = self._segment_config.schema.get_defaults()
            spray_height = float(str(settings.get("spraying_height", _defaults.get("spraying_height", "0"))).replace(",", ""))
            rz_offset = float(settings.get("rz_angle", _defaults.get("rz_angle", "0")))
        except (ValueError, TypeError):
            spray_height = 0.0
            rz_offset = 0.0
        if rz_override is not None:
            rz_offset = float(rz_override)

        base_position = self._resolve_base_position()
        base_z = base_position[2] + spray_height if base_position is not None else self._z_min + spray_height

        if self._resolver is not None:
            from src.engine.robot.targeting import VisionPoseRequest

            resolved_target_name = str(target_point_name or self._target_point_name or "").strip().lower()
            target_point = self._resolver.registry.by_name(resolved_target_name)
            result = self._resolver.resolve(
                VisionPoseRequest(
                    compensated_px,
                    compensated_py,
                    z_mm=base_z,
                    rz_degrees=rz_offset,
                    rx_degrees=180.0,
                    ry_degrees=0.0,
                ),
                target_point,
                frame=str(frame_name or "").strip().lower(),
            )
            return float(result.final_xy[0]), float(result.final_xy[1])

        if self._transformer is None or not self._transformer.is_available():
            return compensated_px, compensated_py
        rx_coord, ry_coord = self._transformer.transform(compensated_px, compensated_py)
        return float(rx_coord), float(ry_coord)

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

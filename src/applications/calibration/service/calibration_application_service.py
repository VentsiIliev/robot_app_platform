import logging
import math
import os
import re
import threading
import time
import json
from typing import Callable, Optional, Protocol, Sequence

import cv2
import numpy as np

from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.calibration_settings.service.i_calibration_settings_service import (
    ICalibrationSettingsService,
)
from src.applications.intrinsic_calibration_capture.service.i_intrinsic_capture_service import (
    IntrinsicCaptureConfig,
)
from src.applications.height_measuring.service.i_height_measuring_app_service import LaserDetectionResult
from src.applications.calibration.service.i_calibration_service import ICalibrationService, RobotCalibrationPreview
from src.applications.calibration.service.calibration_settings_bridge import CalibrationSettingsBridge
from src.engine.robot.calibration.robot_calibration import metrics
from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.robot.calibration.robot_calibration.target_planning import (
    build_partitioned_target_selection_plan,
    build_target_selection_plan,
)
from src.engine.vision.i_vision_service import IVisionService
from src.shared_contracts.declarations import WorkAreaDefinition
from src.engine.work_areas.i_work_area_service import IWorkAreaService

_logger = logging.getLogger(__name__)

_DEFAULT_VELOCITY     = 30
_DEFAULT_ACCELERATION = 10


_GRID_LABEL_RE = re.compile(r"^r(\d+)c(\d+)$")


def _parse_grid_label(label: str) -> tuple[int, int] | None:
    """Return zero-based (row, col) from a label like 'r3c2', or None."""
    m = _GRID_LABEL_RE.match(label)
    if m is None:
        return None
    return int(m.group(1)) - 1, int(m.group(2)) - 1


def _point_in_polygon(px: float, py: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting containment test for a simple polygon."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _format_marker_id_log_block(title: str, marker_ids: list[int] | tuple[int, ...] | set[int]) -> str:
    ids = [int(v) for v in marker_ids]
    ids_text = ", ".join(str(v) for v in ids) if ids else "-"
    return f"{title} ({len(ids)}): [{ids_text}]"


class _IProcessController(Protocol):
    def calibrate(self) -> None: ...
    def stop_calibration(self) -> None: ...


class _IRobotService(Protocol):
    def get_current_position(self) -> list: ...
    def move_ptp(self, position, tool, user, velocity, acceleration, wait_to_reach=False) -> bool: ...
    def stop_motion(self) -> bool: ...
    def validate_pose(
        self,
        start_position,
        target_position,
        tool: int = 0,
        user: int = 0,
        start_joint_state: dict | None = None,
    ) -> dict: ...
    def enable_safety_walls(self) -> bool: ...
    def disable_safety_walls(self) -> bool: ...
    def are_safety_walls_enabled(self) -> Optional[bool]: ...


class _IHeightService(Protocol):
    def is_calibrated(self) -> bool: ...
    def get_calibration_data(self): ...
    def measure_at(self, x: float, y: float, *, already_at_xy: bool = False) -> Optional[float]: ...
    def save_height_map(
        self,
        samples: list[list[float]],
        area_id: str = "",
        marker_ids: Optional[list[int]] = None,
        point_labels: Optional[list[str]] = None,
        grid_rows: int = 0,
        grid_cols: int = 0,
        planned_points: Optional[list[list[float]]] = None,
        planned_point_labels: Optional[list[str]] = None,
        unavailable_point_labels: Optional[list[str]] = None,
    ) -> None: ...
    def get_depth_map_data(self, area_id: str = ""): ...


class _IRobotConfig(Protocol):
    robot_tool: int
    robot_user: int


class _ICalibConfig(Protocol):
    required_ids: list
    z_target: int
    velocity: int
    acceleration: int


class _ICameraTcpOffsetCalibrator(Protocol):
    def calibrate(self) -> tuple[bool, str]: ...

    def stop(self) -> None: ...


class _ICameraZShiftCalibrator(Protocol):
    def calibrate(
        self,
        marker_id: int,
        samples: int,
        z_step_mm: float,
        settle_time_s: float,
    ) -> tuple[bool, str]: ...

    def stop(self) -> None: ...


class _IMarkerHeightMappingService(Protocol):
    def measure_marker_heights(self) -> tuple[bool, str]: ...
    def generate_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> list[tuple[float, float]]: ...
    def measure_area_grid(
        self,
        area_id: str,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
        support_points_mm: list[tuple[str, float, float]] | None = None,
        skip_labels: set[str] | None = None,
        measurement_pose: list[float] | None = None,
    ) -> tuple[bool, str]: ...
    def verify_height_model(
        self,
        area_id: str = "",
        measurement_pose: list[float] | None = None,
    ) -> tuple[bool, str]: ...
    def stop(self) -> None: ...
    def is_ready(self) -> bool: ...


class _ILaserCalibrator(Protocol):
    def calibrate(self, initial_position: list, stop_event: threading.Event | None = None) -> bool: ...


class _ILaserOps(Protocol):
    def detect(self) -> tuple: ...
    def restore(self) -> None: ...


class _IIntrinsicCaptureService(Protocol):
    def start_capture(self) -> None: ...
    def stop_capture(self) -> None: ...
    def is_running(self) -> bool: ...
    def get_config(self) -> IntrinsicCaptureConfig: ...
    def save_config(self, config: IntrinsicCaptureConfig) -> None: ...


class CalibrationApplicationService(ICalibrationService):

    def __init__(self, vision_service: IVisionService, process_controller: _IProcessController,
                 robot_service: _IRobotService = None, height_service: _IHeightService = None,
                 robot_config: _IRobotConfig = None, calib_config: _ICalibConfig = None,
                 transformer: ICoordinateTransformer = None,
                 work_area_service: Optional[IWorkAreaService] = None,
                 camera_tcp_offset_calibrator: Optional[_ICameraTcpOffsetCalibrator] = None,
                 camera_z_shift_calibrator: Optional[_ICameraZShiftCalibrator] = None,
                 marker_height_mapping_service: Optional[_IMarkerHeightMappingService] = None,
                 calibration_settings_service: Optional[ICalibrationSettingsService] = None,
                 laser_calibration_service: Optional[_ILaserCalibrator] = None,
                 laser_ops: Optional[_ILaserOps] = None,
                 intrinsic_capture_service: Optional[_IIntrinsicCaptureService] = None,
                 observer_group_provider: Optional[Callable[[str], str | None]] = None,
                 observer_position_provider: Optional[Callable[[str], list[float] | None]] = None,
                 use_marker_centre: bool = False,
                 work_area_definitions: Optional[list[WorkAreaDefinition]] = None):
        self._vision_service      = vision_service
        self._process_controller  = process_controller
        self._robot_service       = robot_service
        self._height_service      = height_service
        self._robot_config        = robot_config
        self._calib_config        = calib_config
        self._transformer         = transformer
        self._work_area_service   = work_area_service
        self._camera_tcp_offset_calibrator = camera_tcp_offset_calibrator
        self._camera_z_shift_calibrator = camera_z_shift_calibrator
        self._marker_height_mapping_service = marker_height_mapping_service
        self._calibration_settings = CalibrationSettingsBridge(calibration_settings_service)
        self._laser_calibration_service = laser_calibration_service
        self._laser_ops = laser_ops
        self._intrinsic_capture_service = intrinsic_capture_service
        self._observer_group_provider = observer_group_provider
        self._observer_position_provider = observer_position_provider
        self._use_marker_centre   = use_marker_centre
        self._work_area_definitions = list(work_area_definitions or [])
        self._stop_test           = False
        self._stop_laser_calibration = threading.Event()
        self._pending_support_points_mm: list[tuple[str, float, float]] = []
        self._pending_skip_labels: set[str] = set()

    # ── Helpers ───────────────────────────────────────────────────────

    def _robot_tool(self) -> int:
        return self._robot_config.robot_tool if self._robot_config else 0

    def _robot_user(self) -> int:
        return self._robot_config.robot_user if self._robot_config else 0

    def _required_ids(self) -> set | None:
        if self._calib_config is None:
            return None
        return set(self._calib_config.required_ids)

    def _candidate_ids(self) -> set[int]:
        if self._calib_config is None:
            return set()
        candidate_ids = getattr(self._calib_config, "candidate_ids", None)
        if candidate_ids:
            return {int(v) for v in candidate_ids}
        return {int(v) for v in getattr(self._calib_config, "required_ids", [])}

    def _min_target_separation_px(self) -> float:
        if self._calib_config is None:
            return 120.0
        return float(getattr(self._calib_config, "min_target_separation_px", 120.0))

    def _homography_target_count(self) -> int:
        if self._calib_config is None:
            return 16
        return max(4, int(getattr(self._calib_config, "homography_target_count", 16) or 16))

    def _residual_target_count(self) -> int:
        if self._calib_config is None:
            return 10
        return max(0, int(getattr(self._calib_config, "residual_target_count", 10) or 0))

    def _validation_target_count(self) -> int:
        if self._calib_config is None:
            return 6
        return max(0, int(getattr(self._calib_config, "validation_target_count", 6) or 0))

    def _test_target_count(self) -> int:
        if self._calib_config is None:
            return 10
        return max(1, int(getattr(self._calib_config, "test_target_count", 10) or 10))

    def _known_unreachable_marker_ids(self) -> set[int]:
        if self._calib_config is None:
            return set()
        if not bool(getattr(self._calib_config, "auto_skip_known_unreachable_markers", True)):
            return set()
        return {
            int(marker_id)
            for marker_id in (getattr(self._calib_config, "known_unreachable_marker_ids", []) or [])
        }

    def _movement_velocity(self) -> int:
        if self._calib_config is None:
            return _DEFAULT_VELOCITY
        return self._calib_config.velocity

    def _movement_acceleration(self) -> int:
        if self._calib_config is None:
            return _DEFAULT_ACCELERATION
        return self._calib_config.acceleration

    def _load_test_calibration_report(self) -> dict | None:
        if self._vision_service is None:
            return None
        matrix_path = self._vision_service.camera_to_robot_matrix_path
        report_path = metrics.derive_calibration_artifact_paths(matrix_path)["report_path"]
        if not os.path.isfile(report_path):
            return None
        with open(report_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _load_homography_residual_model(self) -> metrics.HomographyResidualModel | metrics.HomographyTPSResidualModel | None:
        if self._vision_service is None:
            return None
        matrix_path = self._vision_service.camera_to_robot_matrix_path
        residual_path = metrics.derive_calibration_artifact_paths(matrix_path)["homography_residual_path"]
        if not os.path.isfile(residual_path):
            return None
        with open(residual_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        basis = payload.get("basis", "quadratic_uv")
        if basis == "tps":
            return metrics.HomographyTPSResidualModel(
                homography_matrix=payload["homography_matrix"],
                support_points=payload["support_points"],
                dx_residuals=payload["dx_residuals"],
                dy_residuals=payload["dy_residuals"],
            )
        return metrics.HomographyResidualModel(
            homography_matrix=np.asarray(payload.get("homography_matrix", []), dtype=np.float64).reshape(3, 3),
            dx_coeffs=np.asarray(payload.get("dx_coeffs", []), dtype=np.float64).reshape(-1),
            dy_coeffs=np.asarray(payload.get("dy_coeffs", []), dtype=np.float64).reshape(-1),
        )

    @staticmethod
    def _training_marker_ids_from_report(report: dict | None) -> set[int]:
        if not report:
            return set()
        metadata = report.get("metadata") or {}
        used_marker_ids = metadata.get("training_marker_ids")
        if used_marker_ids is not None:
            return {int(marker_id) for marker_id in used_marker_ids}
        used_marker_ids = metadata.get("used_marker_ids")
        if used_marker_ids is not None:
            return {int(marker_id) for marker_id in used_marker_ids}
        return {int(label) for label in report.get("point_labels", [])}

    @staticmethod
    def _all_calibration_marker_ids_from_report(report: dict | None) -> set[int]:
        if not report:
            return set()
        metadata = report.get("metadata") or {}
        combined: set[int] = set()
        for key in (
            "training_marker_ids",
            "homography_marker_ids",
            "residual_marker_ids",
            "validation_marker_ids",
            "selected_target_ids",
            "used_marker_ids",
        ):
            values = metadata.get(key)
            if values is not None:
                combined.update(int(marker_id) for marker_id in values)
        if not combined:
            combined.update(int(label) for label in report.get("point_labels", []))
        return combined

    def _predict_robot_xy(self, model_name: str, px: float, py: float) -> tuple[float, float] | None:
        residual_model = None
        if model_name in {"homography", "homography_residual"}:
            residual_model = self._load_homography_residual_model()
        if model_name == "homography_residual":
            if residual_model is None:
                raise RuntimeError("Homography residual artifact is not available")
            prediction = residual_model.predict([float(px), float(py)])
            return float(prediction[0]), float(prediction[1])
        if model_name == "homography" and residual_model is not None:
            prediction = residual_model.predict([float(px), float(py)])
            return float(prediction[0]), float(prediction[1])

        if self._transformer is None:
            raise RuntimeError("Homography transformer unavailable")
        return self._transformer.transform(float(px), float(py))

    def _resolve_observer_pose(self, area_id: str = "") -> list[float] | None:
        resolved_area_id = str(area_id or "").strip()
        if not resolved_area_id:
            return None
        if self._observer_group_provider is None or self._observer_position_provider is None:
            return None
        observer_group = self._observer_group_provider(resolved_area_id)
        if not observer_group:
            return None
        observer_position = self._observer_position_provider(observer_group)
        if observer_position is None or len(observer_position) < 6:
            return None
        return list(observer_position)

    def _resolve_measurement_pose(self, area_id: str = "") -> list[float] | None:
        observer_pose = self._resolve_observer_pose(area_id)
        if observer_pose is not None:
            return observer_pose
        return self._resolve_height_measurement_pose()

    def _resolve_height_measurement_pose(self) -> list[float] | None:
        if self._height_service is None:
            return None
        calib = self._height_service.get_calibration_data()
        if calib is None or not getattr(calib, "robot_initial_position", None):
            return None
        return list(calib.robot_initial_position)

    def _get_active_work_area_polygon_px(self) -> list[tuple[float, float]]:
        area_id = self.get_active_work_area_id()
        if not area_id or self._work_area_service is None or self._vision_service is None:
            return []
        points_norm = self._work_area_service.get_work_area(area_id)
        if not points_norm:
            return []
        width = float(self._vision_service.get_camera_width())
        height = float(self._vision_service.get_camera_height())
        return [
            (float(xn) * width, float(yn) * height)
            for xn, yn in points_norm
        ]

    def _extract_marker_reference_point(self, marker_corners: np.ndarray) -> tuple[float, float]:
        corners_4 = marker_corners[0]
        if self._use_marker_centre:
            px, py = corners_4.mean(axis=0)
        else:
            px, py = corners_4[0]
        return float(px), float(py)

    def _detect_marker_points(
        self,
        frame: np.ndarray,
        *,
        work_area_polygon_px: list[tuple[float, float]] | None = None,
        exclude_ids: set[int] | None = None,
    ) -> dict[int, np.ndarray]:
        corners, ids, _ = self._vision_service.detect_aruco_markers(frame)
        if ids is None or len(ids) == 0:
            return {}
        excluded = {int(v) for v in (exclude_ids or set())}
        polygon = list(work_area_polygon_px or [])
        detected_points: dict[int, np.ndarray] = {}
        for marker_id, marker_corners in zip(ids.flatten(), corners):
            marker_id = int(marker_id)
            if marker_id in excluded:
                continue
            px, py = self._extract_marker_reference_point(marker_corners)
            if len(polygon) >= 3 and not _point_in_polygon(px, py, polygon):
                continue
            detected_points[marker_id] = np.asarray([px, py], dtype=np.float32)
        return detected_points

    def _select_test_marker_ids(self, detected_points: dict[int, np.ndarray], *, target_count: int | None = None) -> tuple[list[int], dict]:
        if not detected_points:
            return [], {"available_ids": [], "selected_ids": []}
        known_unreachable = self._known_unreachable_marker_ids()
        usable_points = {
            int(marker_id): point
            for marker_id, point in detected_points.items()
            if int(marker_id) not in known_unreachable
        }
        if not usable_points:
            return [], {
                "available_ids": sorted(int(marker_id) for marker_id in detected_points),
                "known_unreachable_ids": sorted(known_unreachable),
                "selected_ids": [],
            }
        requested = max(1, int(target_count or self._test_target_count()))
        selection_plan = build_target_selection_plan(
            usable_points,
            image_width=self._vision_service.get_camera_width(),
            image_height=self._vision_service.get_camera_height(),
            min_targets=min(requested, len(usable_points)),
            max_targets=min(requested, len(usable_points)),
            min_target_separation_px=self._min_target_separation_px(),
            preferred_ids=[],
        )
        report = dict(selection_plan.report)
        report["selection_strategy"] = "spread_holdout"
        report["requested_target_count"] = requested
        report["known_unreachable_ids"] = sorted(known_unreachable)
        return list(selection_plan.selected_ids), report

    def _detect_specific_marker_point(
        self,
        marker_id: int,
        *,
        work_area_polygon_px: list[tuple[float, float]] | None = None,
        retries: int = 6,
        retry_delay_s: float = 0.2,
    ) -> tuple[float, float] | None:
        polygon = list(work_area_polygon_px or [])
        for _ in range(max(1, retries)):
            if self._stop_test:
                return None
            frame = self._vision_service.get_latest_frame()
            if frame is None:
                time.sleep(retry_delay_s)
                continue
            corners, ids, _ = self._vision_service.detect_aruco_markers(frame)
            if ids is None or len(ids) == 0:
                time.sleep(retry_delay_s)
                continue
            for detected_id, marker_corners in zip(ids.flatten(), corners):
                if int(detected_id) != int(marker_id):
                    continue
                px, py = self._extract_marker_reference_point(marker_corners)
                if len(polygon) >= 3 and not _point_in_polygon(px, py, polygon):
                    return None
                return px, py
            time.sleep(retry_delay_s)
        return None

    def _save_test_calibration_report(self, model_name: str, payload: dict) -> str | None:
        if self._vision_service is None:
            return None
        matrix_path = self._vision_service.camera_to_robot_matrix_path
        base, _ = os.path.splitext(matrix_path)
        report_path = f"{base}_validation_{model_name}.json"
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return report_path

    def _log_test_calibration_report(self, model_name: str, payload: dict, report_path: str | None) -> None:
        summary = dict(payload.get("summary") or {})
        center_summary = dict(summary.get("center_offset_px") or {})
        center_dx_summary = dict(summary.get("center_offset_dx_px") or {})
        center_dy_summary = dict(summary.get("center_offset_dy_px") or {})
        _logger.info(
            "Test calibration report [%s]: status=%s tested=%s successful=%s failed=%s visible=%s "
            "center_offset_px(mean=%s median=%s max=%s) "
            "dx_px(mean=%s median=%s max=%s) dy_px(mean=%s median=%s max=%s) report=%s",
            model_name,
            summary.get("status"),
            summary.get("tested_count"),
            summary.get("successful_count"),
            summary.get("failed_count"),
            summary.get("visible_count"),
            center_summary.get("mean"),
            center_summary.get("median"),
            center_summary.get("max"),
            center_dx_summary.get("mean"),
            center_dx_summary.get("median"),
            center_dx_summary.get("max"),
            center_dy_summary.get("mean"),
            center_dy_summary.get("median"),
            center_dy_summary.get("max"),
            report_path,
        )
        for row in payload.get("results", []) or []:
            _logger.info(
                "  marker=%s success=%s predicted_xy_mm=%s observed_px=%s center_offset_px=%s center_dist_px=%s robot_xy_mm=%s note=%s",
                row.get("marker_id"),
                row.get("success"),
                row.get("predicted_xy_mm"),
                row.get("observed_marker_point_px"),
                row.get("observed_center_offset_px"),
                row.get("observed_center_distance_px"),
                row.get("robot_xy_mm"),
                row.get("note"),
            )

    @staticmethod
    def _summarize_scalar_values(values: list[float]) -> dict:
        if not values:
            return {"count": 0, "mean": None, "median": None, "max": None}
        array = np.asarray(values, dtype=np.float64)
        return {
            "count": int(array.size),
            "mean": float(np.mean(array)),
            "median": float(np.median(array)),
            "max": float(np.max(array)),
        }

    @staticmethod
    def _summarize_signed_values(values: list[float]) -> dict:
        if not values:
            return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
        array = np.asarray(values, dtype=np.float64)
        return {
            "count": int(array.size),
            "mean": float(np.mean(array)),
            "median": float(np.median(array)),
            "min": float(np.min(array)),
            "max": float(np.max(array)),
        }

    @staticmethod
    def _draw_robot_calibration_preview(
        image: np.ndarray,
        detected_points: dict[int, np.ndarray],
        selected_ids: list[int],
        work_area_polygon_px: list[tuple[float, float]] | None = None,
        *,
        all_detected_points: dict[int, np.ndarray] | None = None,
        report: dict | None = None,
    ) -> None:
        if image is None or image.size == 0:
            return

        selected_set = {int(marker_id) for marker_id in selected_ids}
        all_detected_points = {
            int(marker_id): np.asarray(point, dtype=np.float32).reshape(2)
            for marker_id, point in (all_detected_points or detected_points).items()
        }
        report = dict(report or {})
        homography_set = {int(marker_id) for marker_id in report.get("homography_ids", [])}
        residual_set = {int(marker_id) for marker_id in report.get("residual_ids", [])}
        validation_set = {int(marker_id) for marker_id in report.get("validation_ids", [])}
        known_unreachable_set = {int(marker_id) for marker_id in report.get("known_unreachable_ids", [])}
        polygon = list(work_area_polygon_px or [])

        if len(polygon) >= 3:
            polygon_pts = np.asarray(polygon, dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(image, [polygon_pts], True, (255, 120, 40), 2, cv2.LINE_AA)
            cv2.putText(
                image,
                "Work area",
                tuple(np.int32(polygon_pts[0][0] + np.array([8, -8]))),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 120, 40),
                1,
                cv2.LINE_AA,
            )

        selected_points = [
            np.asarray(detected_points[marker_id], dtype=np.float32).reshape(2)
            for marker_id in selected_ids
            if marker_id in detected_points
        ]

        if len(selected_points) >= 3:
            pts = np.asarray(selected_points, dtype=np.float32)
            hull = cv2.convexHull(pts.reshape(-1, 1, 2))
            cv2.polylines(image, [np.int32(hull)], True, (30, 200, 255), 2, cv2.LINE_AA)

            rect = (0, 0, max(1, image.shape[1]), max(1, image.shape[0]))
            subdiv = cv2.Subdiv2D(rect)
            for point in pts:
                subdiv.insert((float(point[0]), float(point[1])))
            for triangle in subdiv.getTriangleList():
                tri = np.asarray(triangle, dtype=np.float32).reshape(3, 2)
                if np.all(
                    (tri[:, 0] >= 0)
                    & (tri[:, 0] < image.shape[1])
                    & (tri[:, 1] >= 0)
                    & (tri[:, 1] < image.shape[0])
                ):
                    corners = np.int32(tri)
                    cv2.line(image, tuple(corners[0]), tuple(corners[1]), (70, 160, 70), 1, cv2.LINE_AA)
                    cv2.line(image, tuple(corners[1]), tuple(corners[2]), (70, 160, 70), 1, cv2.LINE_AA)
                    cv2.line(image, tuple(corners[2]), tuple(corners[0]), (70, 160, 70), 1, cv2.LINE_AA)

        for marker_id, point in sorted(all_detected_points.items()):
            x, y = int(round(float(point[0]))), int(round(float(point[1])))
            is_candidate = marker_id in detected_points
            is_selected = marker_id in selected_set
            if marker_id in homography_set:
                color = (40, 220, 80)
                label_prefix = "H"
                radius = 8
                thickness = 2
            elif marker_id in residual_set:
                color = (255, 180, 40)
                label_prefix = "R"
                radius = 8
                thickness = 2
            elif marker_id in validation_set:
                color = (40, 180, 255)
                label_prefix = "V"
                radius = 8
                thickness = 2
            elif marker_id in known_unreachable_set:
                color = (60, 60, 220)
                label_prefix = "U"
                radius = 6
                thickness = 2
            elif is_candidate:
                color = (180, 180, 180)
                label_prefix = "D"
                radius = 5
                thickness = 1
            else:
                color = (90, 90, 90)
                label_prefix = "X"
                radius = 4
                thickness = 1
            cv2.circle(image, (x, y), radius, color, thickness, cv2.LINE_AA)
            cv2.putText(
                image,
                f"{label_prefix}:{marker_id}",
                (x + 8, y - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                color,
                1,
                cv2.LINE_AA,
            )

    # ── ICalibrationService ───────────────────────────────────────────

    def load_calibration_settings(self) -> CalibrationSettingsData | None:
        return self._calibration_settings.load()

    def save_calibration_settings(self, settings: CalibrationSettingsData) -> None:
        self._calibration_settings.save(settings)

    def capture_calibration_image(self) -> tuple[bool, str]:
        return self._vision_service.capture_calibration_image()

    def calibrate_camera(self) -> tuple[bool, str]:
        return self._vision_service.calibrate_camera()

    def get_intrinsic_capture_config(self) -> IntrinsicCaptureConfig:
        if self._intrinsic_capture_service is None:
            return IntrinsicCaptureConfig()
        return self._intrinsic_capture_service.get_config()

    def save_intrinsic_capture_config(self, config: IntrinsicCaptureConfig) -> None:
        if self._intrinsic_capture_service is None:
            return
        self._intrinsic_capture_service.save_config(config)

    def start_intrinsic_auto_capture(self) -> tuple[bool, str]:
        if self._intrinsic_capture_service is None:
            return False, "Intrinsic auto capture service unavailable"
        if self._intrinsic_capture_service.is_running():
            return False, "Intrinsic auto capture already running"
        self._intrinsic_capture_service.start_capture()
        return True, "Intrinsic auto capture started"

    def stop_intrinsic_auto_capture(self) -> None:
        if self._intrinsic_capture_service is None:
            return
        self._intrinsic_capture_service.stop_capture()

    def is_intrinsic_auto_capture_running(self) -> bool:
        return bool(self._intrinsic_capture_service is not None and self._intrinsic_capture_service.is_running())

    def calibrate_robot(self) -> tuple[bool, str]:
        if self._process_controller is not None:
            self._process_controller.calibrate()
        return True, "Robot calibration started"

    def preview_robot_calibration(self) -> RobotCalibrationPreview:
        frame = self._vision_service.get_latest_frame()
        if frame is None:
            return RobotCalibrationPreview(
                ok=False,
                message="No camera frame available for robot calibration preview",
            )

        corners, ids, image = self._vision_service.detect_aruco_markers(frame)
        vis = (image if image is not None else frame).copy()
        if ids is None or len(ids) == 0:
            return RobotCalibrationPreview(
                ok=False,
                message="No ArUco markers detected in the current frame",
                frame=vis,
                available_ids=[],
                selected_ids=[],
            )

        candidate_ids = self._candidate_ids()
        work_area_polygon_px = self._get_active_work_area_polygon_px()
        all_detected_points: dict[int, np.ndarray] = {}
        detected_points: dict[int, np.ndarray] = {}
        for marker_id, marker_corners in zip(ids.flatten(), corners):
            marker_id = int(marker_id)
            corners_4 = marker_corners[0]
            ref_pt = corners_4.mean(axis=0) if self._use_marker_centre else corners_4[0]
            all_detected_points[marker_id] = np.asarray(ref_pt, dtype=np.float32)
            if len(work_area_polygon_px) >= 3 and not _point_in_polygon(
                float(ref_pt[0]),
                float(ref_pt[1]),
                work_area_polygon_px,
            ):
                continue
            detected_points[marker_id] = np.asarray(ref_pt, dtype=np.float32)

        if not detected_points:
            if len(work_area_polygon_px) >= 3:
                self._draw_robot_calibration_preview(vis, {}, [], work_area_polygon_px)
            return RobotCalibrationPreview(
                ok=False,
                message=(
                    "No configured candidate markers were detected inside the active work area"
                    if len(work_area_polygon_px) >= 3
                    else "No configured candidate markers were detected in the current frame"
                ),
                frame=vis,
                available_ids=[],
                selected_ids=[],
                report={
                    "all_detected_ids": sorted(all_detected_points),
                    "all_detected_count": len(all_detected_points),
                    "in_work_area_count": 0,
                },
            )

        required_total = (
            self._homography_target_count()
            + self._residual_target_count()
            + self._validation_target_count()
        )
        known_unreachable = self._known_unreachable_marker_ids()
        usable_detected_points = {
            int(marker_id): point
            for marker_id, point in detected_points.items()
            if int(marker_id) not in known_unreachable
        }
        if not usable_detected_points:
            self._draw_robot_calibration_preview(
                vis,
                {},
                [],
                work_area_polygon_px,
                all_detected_points=all_detected_points,
                report={"known_unreachable_ids": sorted(known_unreachable)},
            )
            return RobotCalibrationPreview(
                ok=False,
                message="All detected candidate markers are currently marked as known unreachable",
                frame=vis,
                available_ids=[],
                selected_ids=[],
                report={
                    "all_detected_ids": sorted(all_detected_points),
                    "all_detected_count": len(all_detected_points),
                    "in_work_area_count": len(detected_points),
                    "known_unreachable_ids": sorted(known_unreachable),
                },
            )
        selection_plan = build_partitioned_target_selection_plan(
            usable_detected_points,
            image_width=self._vision_service.get_camera_width(),
            image_height=self._vision_service.get_camera_height(),
            homography_targets=self._homography_target_count(),
            residual_targets=self._residual_target_count(),
            validation_targets=self._validation_target_count(),
            min_target_separation_px=self._min_target_separation_px(),
            preferred_ids=sorted(candidate_ids),
        )
        _logger.info(
            "Robot calibration preview target grid: available_ids=%s auto_skipped_known_unreachable_ids=%s homography_ids=%s residual_ids=%s validation_ids=%s execution_ids=%s work_area_constrained=%s",
            sorted(int(marker_id) for marker_id in usable_detected_points),
            sorted(int(marker_id) for marker_id in known_unreachable if marker_id in detected_points),
            list(selection_plan.homography_ids or []),
            list(selection_plan.residual_ids or []),
            list(selection_plan.validation_ids or []),
            list(selection_plan.selected_ids),
            len(work_area_polygon_px) >= 3,
        )
        _logger.info(
            "Robot calibration preview details:\n%s\n%s\n%s\n%s\n%s\n%s\n%s",
            _format_marker_id_log_block("Homography", selection_plan.homography_ids or []),
            _format_marker_id_log_block("Residual", selection_plan.residual_ids or []),
            _format_marker_id_log_block("Validation", selection_plan.validation_ids or []),
            _format_marker_id_log_block("Selected total", selection_plan.selected_ids),
            _format_marker_id_log_block("In work area", sorted(int(marker_id) for marker_id in detected_points)),
            _format_marker_id_log_block("Known unreachable", sorted(int(marker_id) for marker_id in known_unreachable)),
            _format_marker_id_log_block("All detected", sorted(int(marker_id) for marker_id in all_detected_points)),
        )
        self._draw_robot_calibration_preview(
            vis,
            usable_detected_points,
            selection_plan.selected_ids,
            work_area_polygon_px,
            all_detected_points=all_detected_points,
            report={
                **selection_plan.report,
                "known_unreachable_ids": sorted(known_unreachable),
            },
        )
        ok = (
            len(selection_plan.homography_ids or []) >= self._homography_target_count()
            and len(selection_plan.residual_ids or []) >= self._residual_target_count()
            and len(selection_plan.validation_ids or []) >= self._validation_target_count()
        )
        message = (
            f"Detected {len(detected_points)} candidate markers"
            f"{' inside the active work area' if len(work_area_polygon_px) >= 3 else ''}"
            f" and selected {len(selection_plan.selected_ids)} targets"
            if ok else
            f"Only {len(selection_plan.selected_ids)} targets available; need H={self._homography_target_count()}, R={self._residual_target_count()}, V={self._validation_target_count()} (total {required_total})"
        )
        return RobotCalibrationPreview(
            ok=ok,
            message=message,
            frame=vis,
            available_ids=sorted(usable_detected_points),
            selected_ids=list(selection_plan.selected_ids),
            report={
                **selection_plan.report,
                "all_detected_ids": sorted(all_detected_points),
                "all_detected_count": len(all_detected_points),
                "in_work_area_count": len(detected_points),
                "known_unreachable_ids": sorted(known_unreachable),
            },
        )

    def calibrate_camera_and_robot(self) -> tuple[bool, str]:
        ok, msg = self.calibrate_camera()
        if not ok:
            return False, f"Camera calibration failed: {msg}"
        if self._process_controller is not None:
            self._process_controller.calibrate()
        return True, "Camera calibrated — robot calibration started"

    def calibrate_camera_tcp_offset(self) -> tuple[bool, str]:
        if not self.is_calibrated():
            return False, "System not calibrated — run robot calibration first"
        if self._camera_tcp_offset_calibrator is None:
            return False, "Camera TCP offset calibration is not configured"
        return self._camera_tcp_offset_calibrator.calibrate()

    def calibrate_camera_z_shift(
        self,
        marker_id: int,
        samples: int,
        z_step_mm: float,
        settle_time_s: float,
    ) -> tuple[bool, str]:
        if not self.is_calibrated():
            return False, "System not calibrated — run robot calibration first"
        if self._camera_z_shift_calibrator is None:
            return False, "Camera Z shift calibration is not configured"
        return self._camera_z_shift_calibrator.calibrate(
            marker_id,
            samples,
            z_step_mm,
            settle_time_s,
        )

    def calibrate_laser(self) -> tuple[bool, str]:
        if self._laser_calibration_service is None:
            return False, "Laser calibration is not configured"
        self._stop_laser_calibration.clear()
        try:
            current_pos = None
            if self._robot_service is not None:
                current_pos = self._robot_service.get_current_position()
            initial_pos = list(current_pos) if current_pos else None
            ok = self._laser_calibration_service.calibrate(
                initial_pos,
                stop_event=self._stop_laser_calibration,
            )
            if ok and self._height_service is not None:
                self._height_service.reload_calibration()
                return True, "Laser calibration complete"
            if self._stop_laser_calibration.is_set():
                return False, "Laser calibration cancelled"
            return False, "Laser calibration failed — check laser and robot position"
        except Exception as exc:
            _logger.error("Laser calibration error: %s", exc)
            return False, f"Laser calibration error: {exc}"

    def detect_laser_once(self) -> LaserDetectionResult:
        if self._laser_ops is None:
            return LaserDetectionResult(ok=False, message="Laser detection not available")
        try:
            mask, _, closest = self._laser_ops.detect()
            if closest is not None:
                x, y = closest
                return LaserDetectionResult(
                    ok=True,
                    message=f"Detected at ({x:.1f}, {y:.1f})",
                    pixel_coords=(float(x), float(y)),
                    height_mm=self._estimate_laser_height(float(x)),
                    debug_image=self._build_laser_debug_image(mask, closest),
                    mask=mask,
                )
            return LaserDetectionResult(ok=False, message="No laser line detected", mask=mask)
        except Exception as exc:
            _logger.error("Laser detection error: %s", exc)
            return LaserDetectionResult(ok=False, message=f"Laser detection error: {exc}")

    def stop_calibration(self) -> None:
        if self._process_controller is not None:
            self._process_controller.stop_calibration()
        self._stop_laser_calibration.set()
        if self._camera_tcp_offset_calibrator is not None:
            self._camera_tcp_offset_calibrator.stop()
        if self._camera_z_shift_calibrator is not None:
            self._camera_z_shift_calibrator.stop()
        if self._marker_height_mapping_service is not None:
            self._marker_height_mapping_service.stop()

    def ensure_active_work_area_observed(self) -> tuple[bool, str]:
        area_id = self.get_active_work_area_id()
        if not area_id:
            return False, "Select a work area first"
        if self._observer_group_provider is None or self._observer_position_provider is None:
            return True, ""
        observer_group = self._observer_group_provider(area_id)
        if not observer_group:
            return True, ""
        if self._robot_service is None:
            return False, f"Move the robot to the '{observer_group}' observer position first"
        observer_position = self._observer_position_provider(observer_group)
        if not observer_position or len(observer_position) < 6:
            return False, f"Observer position '{observer_group}' is not configured"
        current_position = self._robot_service.get_current_position()
        if not current_position or len(current_position) < 6:
            return False, "Failed to get current robot position"

        linear_tolerance_mm = 5.0
        angular_tolerance_deg = 2.0
        linear_ok = all(
            abs(float(current_position[i]) - float(observer_position[i])) <= linear_tolerance_mm
            for i in range(3)
        )
        angular_ok = all(
            abs(float(current_position[i]) - float(observer_position[i])) <= angular_tolerance_deg
            for i in range(3, 6)
        )
        if linear_ok and angular_ok:
            return True, ""
        return False, f"Move to the observer position '{observer_group}' first"

    def is_calibrated(self) -> bool:
        if self._vision_service is None:
            return False
        robot_matrix = self._vision_service.camera_to_robot_matrix_path
        storage_dir = os.path.dirname(robot_matrix)
        camera_matrix = os.path.join(storage_dir, "camera_calibration.npz")
        return os.path.isfile(robot_matrix) and os.path.isfile(camera_matrix)

    def test_calibration(self, model_name: str = "homography") -> tuple[bool, str]:
        self._stop_test = False

        if self._vision_service is None:
            return False, "Vision service unavailable"
        if self._robot_service is None:
            return False, "Robot service unavailable"

        model_name = str(model_name or "homography").strip().lower()
        if model_name not in {"homography", "homography_residual"}:
            return False, f"Unsupported test calibration model: {model_name}"

        auto_brightness_locked = False
        auto_brightness_adjustment_locked = False
        try:
            if self._vision_service.get_auto_brightness_enabled():
                auto_brightness_locked = self._vision_service.lock_auto_brightness_region()
                if auto_brightness_locked:
                    _logger.info("Locking auto brightness region during test calibration")
                else:
                    _logger.warning("Unable to lock auto brightness region during test calibration")
                self._vision_service.lock_auto_brightness_adjustment()
                auto_brightness_adjustment_locked = True
                _logger.info("Freezing auto brightness adjustment during test calibration")

            frame = self._vision_service.get_latest_frame()
            if frame is None:
                return False, "No camera frame available"

            if self._transformer is not None:
                self._transformer.reload()
            if self._transformer is None or not self._transformer.is_available():
                return False, "System not calibrated — run calibration first"

            report = self._load_test_calibration_report()
            training_ids = self._training_marker_ids_from_report(report)
            calibration_used_ids = self._all_calibration_marker_ids_from_report(report)
            work_area_polygon_px = self._get_active_work_area_polygon_px()

            current_pos = self._robot_service.get_current_position()
            if not current_pos or len(current_pos) < 6:
                return False, "Failed to get current robot position"

            rx, ry, rz = current_pos[3], current_pos[4], current_pos[5]
            tool     = self._robot_tool()
            user     = self._robot_user()
            velocity = self._movement_velocity()
            accel    = self._movement_acceleration()
            z_target = self._calib_config.z_target if self._calib_config else 300
            image_center_px = (
                float(self._vision_service.get_camera_width()) / 2.0,
                float(self._vision_service.get_camera_height()) / 2.0,
            )

            _logger.info(
                "test_calibration: model=%s tool=%d user=%d vel=%d acc=%d z=%d training_ids=%s excluded_ids=%s",
                model_name, tool, user, velocity, accel, z_target, sorted(training_ids), sorted(calibration_used_ids),
            )
            if model_name == "homography":
                effective_model = "homography_residual" if self._load_homography_residual_model() is not None else "homography"
                _logger.info("test_calibration: effective_model=%s", effective_model)

            detected_points = self._detect_marker_points(
                frame,
                work_area_polygon_px=work_area_polygon_px,
                exclude_ids=calibration_used_ids,
            )
            if not detected_points:
                return False, "No non-calibration ArUco markers detected in the active work area"

            known_unreachable = self._known_unreachable_marker_ids()
            selected_test_ids = sorted(
                mk for mk in (int(m) for m in detected_points.keys())
                if mk not in known_unreachable
            )
            selection_report = {
                "available_ids": sorted(int(m) for m in detected_points),
                "known_unreachable_ids": sorted(known_unreachable),
                "selected_ids": selected_test_ids,
                "selection_strategy": "all_ascending",
            }
            _logger.info(
                "Test calibration targets: available_ids=%s selected_ids=%s training_ids=%s excluded_ids=%s model=%s",
                sorted(int(m) for m in detected_points.keys()),
                selected_test_ids,
                sorted(int(m) for m in training_ids),
                sorted(int(m) for m in calibration_used_ids),
                model_name,
            )
            if not selected_test_ids:
                return False, "No non-training test markers selected"

            marker_results: list[dict] = []
            for marker_id in selected_test_ids:
                if self._stop_test:
                    break

                px, py = detected_points[marker_id]
                prediction = self._predict_robot_xy(model_name, float(px), float(py))
                if prediction is None:
                    marker_results.append({
                        "marker_id": int(marker_id),
                        "success": False,
                        "note": "model did not return a prediction for this marker",
                    })
                    _logger.info("Skipping test marker %d — model produced no prediction", marker_id)
                    continue

                x_mm, y_mm = prediction
                _logger.info(
                    "Test calibration move: marker=%d model=%s predicted_xy=(%.3f, %.3f)",
                    marker_id, model_name, x_mm, y_mm,
                )
                ok = self._robot_service.move_ptp(
                    position=[x_mm, y_mm, z_target, rx, ry, rz],
                    tool=tool,
                    user=user,
                    velocity=velocity,
                    acceleration=accel,
                    wait_to_reach=True,
                )
                if not ok:
                    marker_results.append({
                        "marker_id": int(marker_id),
                        "success": False,
                        "note": "initial move failed",
                    })
                    continue

                time.sleep(0.8)
                observed_point = self._detect_specific_marker_point(
                    marker_id,
                    work_area_polygon_px=work_area_polygon_px,
                )
                current_robot_pos = self._robot_service.get_current_position()
                observed_center_offset_px = None
                observed_center_distance_px = None
                if observed_point is not None:
                    observed_center_offset_px = [
                        float(observed_point[0] - image_center_px[0]),
                        float(observed_point[1] - image_center_px[1]),
                    ]
                    observed_center_distance_px = float(
                        np.linalg.norm(np.asarray(observed_center_offset_px, dtype=np.float64))
                    )
                result = {
                    "marker_id": int(marker_id),
                    "success": True,
                    "predicted_xy_mm": [float(x_mm), float(y_mm)],
                    "observed_marker_point_px": (
                        [float(observed_point[0]), float(observed_point[1])]
                        if observed_point is not None else None
                    ),
                    "image_center_px": [float(image_center_px[0]), float(image_center_px[1])],
                    "observed_center_offset_px": observed_center_offset_px,
                    "observed_center_distance_px": observed_center_distance_px,
                    "robot_xy_mm": (
                        [float(current_robot_pos[0]), float(current_robot_pos[1])]
                        if current_robot_pos and len(current_robot_pos) >= 2 else None
                    ),
                    "note": (
                        "visual inspection target reached"
                        if observed_point is not None
                        else "marker not visible after move"
                    ),
                }
                marker_results.append(result)
                _logger.info(
                    "Test calibration result: marker=%d success=%s observed_point=%s center_offset_px=%s center_dist_px=%s robot_xy=%s note=%s",
                    marker_id,
                    result.get("success"),
                    result.get("observed_marker_point_px"),
                    result.get("observed_center_offset_px"),
                    result.get("observed_center_distance_px"),
                    result.get("robot_xy_mm"),
                    result.get("note"),
                )

            successful = [row for row in marker_results if row.get("success")]
            visible = [row for row in marker_results if row.get("observed_center_distance_px") is not None]
            center_distances = [
                float(row["observed_center_distance_px"])
                for row in visible
            ]
            center_dx = [
                float(row["observed_center_offset_px"][0])
                for row in visible
            ]
            center_dy = [
                float(row["observed_center_offset_px"][1])
                for row in visible
            ]
            summary = {
                "status": "stopped" if self._stop_test else "completed",
                "tested_count": len(marker_results),
                "successful_count": len(successful),
                "failed_count": len(marker_results) - len(successful),
                "visible_count": len(visible),
                "center_offset_px": self._summarize_scalar_values(center_distances),
                "center_offset_dx_px": self._summarize_signed_values(center_dx),
                "center_offset_dy_px": self._summarize_signed_values(center_dy),
            }
            report_payload = {
                "model": model_name,
                "selected_test_ids": [int(m) for m in selected_test_ids],
                "training_ids": sorted(int(m) for m in training_ids),
                "excluded_calibration_ids": sorted(int(m) for m in calibration_used_ids),
                "selection_report": selection_report,
                "image_center_px": [float(image_center_px[0]), float(image_center_px[1])],
                "results": marker_results,
                "summary": summary,
            }
            report_path = self._save_test_calibration_report(model_name, report_payload)
            self._log_test_calibration_report(model_name, report_payload, report_path)
            if not successful:
                return False, f"No test markers were reached successfully using {model_name}"
            return True, (
                f"Test {'stopped' if self._stop_test else 'complete'} using {model_name} on "
                f"{len(successful)}/{len(marker_results)} markers for visual inspection"
                + (f", report={report_path}" if report_path else "")
            )
        finally:
            if auto_brightness_adjustment_locked:
                _logger.info("Restoring adaptive auto brightness adjustment after test calibration")
                self._vision_service.unlock_auto_brightness_adjustment()
            if auto_brightness_locked:
                _logger.info("Restoring dynamic auto brightness region after test calibration")
                self._vision_service.unlock_auto_brightness_region()

    def stop_test_calibration(self) -> None:
        self._stop_test = True

    def measure_marker_heights(self) -> tuple[bool, str]:
        if not self.is_calibrated():
            return False, "System not calibrated — run robot calibration first"
        if self._marker_height_mapping_service is None:
            return False, "Marker height mapping is not configured"
        return self._marker_height_mapping_service.measure_marker_heights()

    def get_work_area_definitions(self) -> list[WorkAreaDefinition]:
        return list(self._work_area_definitions)

    def get_active_work_area_id(self) -> str:
        if self._work_area_service is None:
            return ""
        return self._work_area_service.get_active_area_id() or ""

    def set_active_work_area_id(self, area_id: str) -> None:
        if self._work_area_service is None:
            return
        self._work_area_service.set_active_area_id(area_id)
        if self._vision_service is not None:
            try:
                self._vision_service.set_active_work_area(area_id)
            except Exception:
                pass

    def save_height_mapping_area(
        self,
        area_key: str,
        corners_norm: Sequence[tuple[float, float]],
    ) -> tuple[bool, str]:
        if self._work_area_service is None:
            return False, "Work area service unavailable"
        return self._work_area_service.save_work_area(
            area_key,
            [(float(x), float(y)) for x, y in corners_norm],
        )

    def get_height_mapping_area(self, area_key: str) -> list[tuple[float, float]]:
        if self._work_area_service is None:
            return []
        points = self._work_area_service.get_work_area(area_key)
        if not points:
            return []
        return [(float(x), float(y)) for x, y in points]

    def generate_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> list[tuple[float, float]]:
        if self._marker_height_mapping_service is None:
            return []
        return self._marker_height_mapping_service.generate_area_grid(corners_norm, rows, cols)

    def measure_area_grid(
        self,
        area_id: str,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> tuple[bool, str]:
        if not self.is_calibrated():
            return False, "System not calibrated — run robot calibration first"
        if self._marker_height_mapping_service is None:
            return False, "Area grid height mapping is not configured"
        support = list(self._pending_support_points_mm)
        skip = set(self._pending_skip_labels)
        if support:
            _logger.info(
                "measure_area_grid: injecting %d support point(s) from last verification: %s",
                len(support),
                [lbl for lbl, _, _ in support],
            )
        if skip:
            _logger.info(
                "measure_area_grid: pre-skipping %d known-unreachable point(s): %s",
                len(skip), sorted(skip),
            )
        measurement_pose = self._resolve_measurement_pose(area_id)
        if measurement_pose is None:
            return False, "Height measurement calibration pose is unavailable"
        return self._marker_height_mapping_service.measure_area_grid(
            area_id,
            corners_norm, rows, cols,
            support_points_mm=support or None,
            skip_labels=skip or None,
            measurement_pose=measurement_pose,
        )

    def verify_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
        progress_callback: Callable[[str, str, int, int], None] | None = None,
    ) -> tuple[bool, str, dict]:
        if not self.is_calibrated():
            return False, "System not calibrated — run robot calibration first", {}
        if self._robot_service is None:
            return False, "Robot service unavailable", {}
        if self._height_service is None or not self._height_service.is_calibrated():
            return False, "Height measuring is not calibrated", {}
        if self._transformer is None:
            return False, "Homography transformer unavailable", {}
        if rows < 2 or cols < 2:
            return False, "Grid rows and cols must both be at least 2", {}
        if len(corners_norm) != 4:
            return False, "Exactly 4 area corners are required", {}

        self._transformer.reload()
        if not self._transformer.is_available():
            return False, "System not calibrated — run robot calibration first", {}

        points = self.generate_area_grid(corners_norm, rows, cols)
        if not points:
            return False, "Failed to generate area grid points", {}

        area_id = self.get_active_work_area_id()
        measurement_pose = self._resolve_height_measurement_pose()
        if measurement_pose is None or len(measurement_pose) < 6:
            return False, "Height measurement calibration pose is unavailable", {}

        pose_suffix = [
            float(measurement_pose[2]),
            float(measurement_pose[3]),
            float(measurement_pose[4]),
            float(measurement_pose[5]),
        ]
        current = self._robot_service.get_current_position()
        if not current or len(current) < 6:
            return False, "Failed to get current robot position", {}

        anchor_state = None
        point_states = []
        width = float(self._vision_service.get_camera_width())
        height = float(self._vision_service.get_camera_height())
        for index, (xn, yn) in enumerate(points):
            row_idx = index // cols
            col_idx = index % cols
            px = xn * width
            py = yn * height
            x_mm, y_mm = self._transformer.transform(float(px), float(py))
            state = [float(x_mm), float(y_mm), *pose_suffix]
            label = f"r{row_idx + 1}c{col_idx + 1}"
            point_states.append((label, state))
            if anchor_state is None:
                anchor_state = state

        area_corners_robot_xy: list[tuple[float, float]] = [
            self._transformer.transform(float(xn * width), float(yn * height))
            for xn, yn in corners_norm
        ]
        existing_grid_xy = [(float(s[0]), float(s[1])) for _, s in point_states]
        # label → list of normalised pixel coords (one entry per support point found)
        substitutes: dict[str, list[tuple[float, float]]] = {}
        substitute_polygons: dict[str, list[tuple[float, float]]] = {}
        # label → list of robot XY (one entry per support point found)
        substitute_robot_xy: dict[str, list[tuple[float, float]]] = {}

        simulated_state = [
            float(current[0]),
            float(current[1]),
            float(current[2]),
            float(current[3]),
            float(current[4]),
            float(current[5]),
        ]
        tool = self._robot_tool()
        user = self._robot_user()
        unreachable_labels: list[str] = []
        via_anchor_labels: list[str] = []
        reachable_labels: list[str] = []
        walls_were_enabled = False
        validation_cache: dict[tuple[tuple[float, ...], tuple[float, ...]], dict] = {}
        state_joint_seeds: dict[tuple[float, ...], dict] = {}

        def _state_key(state: Sequence[float]) -> tuple[float, ...]:
            return tuple(round(float(v), 3) for v in state[:6])

        def _is_same_state(a: Sequence[float], b: Sequence[float]) -> bool:
            return _state_key(a) == _state_key(b)

        def _validate_cached(
            start_state: Sequence[float],
            target_state: Sequence[float],
            start_joint_state: dict | None = None,
        ) -> dict:
            if _is_same_state(start_state, target_state):
                return {
                    "reachable": True,
                    "reason": "same_state",
                    "target_joint_state": (
                        state_joint_seeds.get(_state_key(start_state)) or start_joint_state
                    ),
                }
            cache_key = (_state_key(start_state), _state_key(target_state))
            cached = validation_cache.get(cache_key)
            if cached is not None:
                return cached
            result = self._robot_service.validate_pose(
                list(start_state),
                list(target_state),
                tool=tool,
                user=user,
                start_joint_state=start_joint_state or state_joint_seeds.get(_state_key(start_state)),
            )
            _logger.info(
                "Area grid reachability validation: start=%s target=%s tool=%s user=%s reachable=%s reason=%s result=%s",
                [round(float(v), 3) for v in start_state[:6]],
                [round(float(v), 3) for v in target_state[:6]],
                tool,
                user,
                result.get("reachable"),
                result.get("reason"),
                result,
            )
            if bool(result.get("reachable")) and isinstance(result.get("target_joint_state"), dict):
                state_joint_seeds[_state_key(target_state)] = result["target_joint_state"]
            validation_cache[cache_key] = result
            return result

        try:
            walls_enabled = self._robot_service.are_safety_walls_enabled()
            walls_were_enabled = bool(walls_enabled)
            if walls_were_enabled and not self._robot_service.disable_safety_walls():
                return False, "Failed to disable safety walls before grid verification", {}

            total = len(point_states)
            anchor_joint_seed: dict | None = None
            if anchor_state is None:
                return False, "Failed to determine grid anchor point", {}

            _logger.info(
                "Area grid verification started: area_id=%s current_pose=%s anchor_pose=%s points=%d pose_suffix=%s",
                area_id,
                [round(float(v), 3) for v in simulated_state[:6]],
                [round(float(v), 3) for v in anchor_state[:6]],
                total,
                [round(float(v), 3) for v in pose_suffix],
            )
            to_anchor = _validate_cached(simulated_state, anchor_state, None)
            if not bool(to_anchor.get("reachable")):
                _logger.warning(
                    "Area grid verification anchor unreachable: area_id=%s current_pose=%s anchor_pose=%s result=%s",
                    area_id,
                    [round(float(v), 3) for v in simulated_state[:6]],
                    [round(float(v), 3) for v in anchor_state[:6]],
                    to_anchor,
                )
                reason = str(to_anchor.get("reason") or "").strip()
                if reason == "target_pose_ik_failed":
                    message = "Grid anchor pose is not reachable with the height-measuring pose"
                else:
                    message = "Current pose cannot reach the grid anchor point"
                return False, message, {
                    "reachable_labels": [],
                    "direct_labels": [],
                    "via_anchor_labels": [],
                    "unreachable_labels": [label for label, _ in point_states],
                }
            anchor_joint_seed = to_anchor.get("target_joint_state")
            state_joint_seeds[_state_key(anchor_state)] = anchor_joint_seed

            for index, (label, target_state) in enumerate(point_states, start=1):
                if _is_same_state(anchor_state, target_state):
                    status = "direct"
                    reachable_labels.append(label)
                else:
                    result = _validate_cached(anchor_state, target_state, anchor_joint_seed)
                    if bool(result.get("reachable")):
                        status = "direct"
                        reachable_labels.append(label)
                    else:
                        status = "unreachable"
                        unreachable_labels.append(label)
                        sub_results = self.find_substitute_points(
                            unreachable_xy=(float(target_state[0]), float(target_state[1])),
                            unreachable_label=label,
                            point_states=point_states,
                            area_corners_robot_xy=area_corners_robot_xy,
                            existing_grid_xy=existing_grid_xy,
                            pose_suffix=pose_suffix,
                            anchor_state=anchor_state,
                            anchor_joint_seed=anchor_joint_seed,
                            tool=tool,
                            user=user,
                        )
                        if sub_results:
                            ux, uy = float(target_state[0]), float(target_state[1])
                            subs_norm: list[tuple[float, float]] = []
                            subs_xy: list[tuple[float, float]] = []
                            for i, (sub_x, sub_y, search_r) in enumerate(sub_results):
                                subs_xy.append((sub_x, sub_y))
                                try:
                                    sub_px, sub_py = self._transformer.inverse_transform(sub_x, sub_y)
                                    subs_norm.append((sub_px / width, sub_py / height))
                                except Exception:
                                    subs_norm.append((-1.0, -1.0))
                                n_pts = 24
                                poly_norm = []
                                for k in range(n_pts):
                                    angle = 2 * math.pi * k / n_pts
                                    try:
                                        cpx, cpy = self._transformer.inverse_transform(
                                            ux + search_r * math.cos(angle),
                                            uy + search_r * math.sin(angle),
                                        )
                                        poly_norm.append((cpx / width, cpy / height))
                                    except Exception:
                                        pass
                                if poly_norm:
                                    substitute_polygons[f"{label}_{i}"] = poly_norm
                            substitutes[label] = subs_norm
                            substitute_robot_xy[label] = subs_xy
                if progress_callback is not None:
                    progress_callback(label, status, index, total)
        finally:
            if walls_were_enabled:
                self._robot_service.enable_safety_walls()

        point_robot_xy: dict[str, tuple[float, float]] = {
            label: (float(state[0]), float(state[1])) for label, state in point_states
        }

        self._pending_support_points_mm = [
            (f"{lbl}_support_{i}", float(sx), float(sy))
            for lbl, pts in substitute_robot_xy.items()
            for i, (sx, sy) in enumerate(pts)
        ]
        self._pending_skip_labels = set(unreachable_labels)

        summary = (
            f"Grid verification complete — reachable {len(reachable_labels)}, "
            f"unreachable {len(unreachable_labels)}"
        )
        details = {
            "reachable_labels": reachable_labels,
            "direct_labels": reachable_labels,
            "via_anchor_labels": via_anchor_labels,
            "unreachable_labels": unreachable_labels,
            "substitutes": substitutes,
            "substitute_polygons": substitute_polygons,
            "point_robot_xy": point_robot_xy,
            "substitute_robot_xy": substitute_robot_xy,
        }
        return True, summary, details

    def find_substitute_points(
        self,
        unreachable_xy: tuple[float, float],
        unreachable_label: str,
        point_states: list[tuple[str, list[float]]],
        area_corners_robot_xy: list[tuple[float, float]],
        existing_grid_xy: list[tuple[float, float]],
        pose_suffix: list[float],
        anchor_state: Sequence[float],
        anchor_joint_seed: dict | None,
        tool: int,
        user: int,
        max_substitutes: int = 2,
        step_mm: float = 10.0,
        max_radius_mm: float = 150.0,
    ) -> list[tuple[float, float, float]]:
        """Find up to *max_substitutes* reachable support points near an unreachable grid point.

        Strategy
        --------
        1. **Column search** — find the nearest same-column grid neighbour, build a
           cell-band polygon spanning that neighbour row to the unreachable row (±1 col),
           then divide the segment [neighbour → unreachable] into *max_substitutes + 1*
           equal parts and validate each interior point.
        2. **Spiral fallback** — if column search finds nothing, search outward in
           expanding rings of *step_mm* (8 angles per ring).

        In both phases the search polygon is the cell-band (when a column neighbour
        exists) so candidates can never escape past the neighbouring row.

        Returns list of (x_mm, y_mm, dist_from_unreachable_mm).
        """
        if self._robot_service is None:
            return []

        ux, uy = unreachable_xy
        min_dist_sq = (step_mm * 0.5) ** 2

        # --- helpers ---
        def _state_xy(row: int, col: int) -> tuple[float, float] | None:
            lbl = f"r{row + 1}c{col + 1}"
            for l, s in point_states:
                if l == lbl:
                    return float(s[0]), float(s[1])
            return None

        def _valid(cx: float, cy: float, poly: list[tuple[float, float]]) -> bool:
            if not _point_in_polygon(cx, cy, poly):
                return False
            if any((cx - gx) ** 2 + (cy - gy) ** 2 < min_dist_sq for gx, gy in existing_grid_xy):
                return False
            r = self._robot_service.validate_pose(
                list(anchor_state), [cx, cy, *pose_suffix],
                tool=tool, user=user, start_joint_state=anchor_joint_seed,
            )
            return bool(r.get("reachable"))

        results: list[tuple[float, float, float]] = []
        search_polygon: list[tuple[float, float]] = area_corners_robot_xy  # default

        # ── 1. Column-aligned search ──────────────────────────────────────────
        parsed_u = _parse_grid_label(unreachable_label)
        if parsed_u is not None:
            row_u, col_u = parsed_u

            same_col: list[tuple[int, int, float, float]] = []
            for lbl, state in point_states:
                p = _parse_grid_label(lbl)
                if p is None or p[1] != col_u or lbl == unreachable_label:
                    continue
                same_col.append((abs(p[0] - row_u), p[0], float(state[0]), float(state[1])))
            same_col.sort(key=lambda t: t[0])

            if same_col:
                _, row_n, nx, ny = same_col[0]  # nearest column neighbour

                # Build cell-band polygon: rows [row_n .. row_u], cols [col_u-1 .. col_u+1]
                band_pts: list[tuple[float, float]] = []
                for bc in (col_u - 1, col_u, col_u + 1):
                    for br in (row_n, row_u):
                        pt = _state_xy(br, bc)
                        if pt is not None:
                            band_pts.append(pt)
                # Deduplicate then sort by angle around centroid → convex polygon
                seen: set[tuple[float, float]] = set()
                unique_pts = [p for p in band_pts if not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]
                if len(unique_pts) >= 3:
                    cx_c = sum(p[0] for p in unique_pts) / len(unique_pts)
                    cy_c = sum(p[1] for p in unique_pts) / len(unique_pts)
                    unique_pts.sort(key=lambda p: math.atan2(p[1] - cy_c, p[0] - cx_c))
                    search_polygon = unique_pts
                    _logger.debug(
                        "find_substitute_points: cell-band polygon for %s has %d vertices",
                        unreachable_label, len(unique_pts),
                    )

            for _, _row_n, nx, ny in same_col:
                if len(results) >= max_substitutes:
                    break
                remaining = max_substitutes - len(results)
                for k in range(1, remaining + 1):
                    t = k / (remaining + 1)
                    cx = nx + t * (ux - nx)
                    cy = ny + t * (uy - ny)
                    if _valid(cx, cy, search_polygon):
                        results.append((cx, cy, math.hypot(cx - ux, cy - uy)))
                if results:
                    break  # found from this neighbor — done with column phase


        return results

    def stop_marker_height_measurement(self) -> None:
        if self._marker_height_mapping_service is not None:
            self._marker_height_mapping_service.stop()

    def can_measure_marker_heights(self) -> bool:
        if not self.is_calibrated():
            return False
        if self._marker_height_mapping_service is None:
            return False
        return self._marker_height_mapping_service.is_ready()

    def verify_height_model(self, area_id: str = "") -> tuple[bool, str]:
        if self._marker_height_mapping_service is None:
            return False, "Marker height mapping is not configured"
        measurement_pose = self._resolve_measurement_pose(area_id)
        if measurement_pose is None:
            return False, "Height measurement calibration pose is unavailable"
        return self._marker_height_mapping_service.verify_height_model(
            area_id,
            measurement_pose=measurement_pose,
        )

    def has_saved_height_model(self, area_id: str = "") -> bool:
        data = self.get_height_calibration_data(area_id)
        return bool(data is not None and data.has_data())

    def get_height_calibration_data(self, area_id: str = ""):
        if self._height_service is None:
            return None
        return self._height_service.get_depth_map_data(area_id)

    def restore_pending_safety_walls(self) -> bool:
        if self._marker_height_mapping_service is None:
            return False
        restore = getattr(self._marker_height_mapping_service, "restore_pending_safety_walls", None)
        if restore is None:
            return False
        return bool(restore())

    def _build_laser_debug_image(self, mask: Optional[np.ndarray], closest: Optional[tuple]) -> np.ndarray:
        frame = self._vision_service.get_latest_frame() if self._vision_service is not None else None
        base = frame.copy() if frame is not None else np.zeros((480, 640, 3), dtype=np.uint8)
        if mask is not None:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 9))
            mask_dilated = cv2.dilate(mask, kernel)
            green_channel = np.zeros_like(base)
            green_channel[:, :, 1] = mask_dilated
            base = cv2.addWeighted(base, 1.0, green_channel, 1.0, 0)
        if closest is not None:
            cx, cy = int(closest[0]), int(closest[1])
            cv2.circle(base, (cx, cy), 8, (0, 0, 255), 2)
            cv2.drawMarker(base, (cx, cy), (0, 0, 255), cv2.MARKER_CROSS, 20, 2)
        return base

    def _estimate_laser_height(self, pixel_x: float) -> Optional[float]:
        if self._height_service is None:
            return None
        data = self._height_service.get_calibration_data()
        if data is None or not data.is_calibrated():
            return None
        delta = data.zero_reference_coords[0] - pixel_x
        features = [delta ** (i + 1) for i in range(data.polynomial_degree)]
        raw_height = sum(c * f for c, f in zip(data.polynomial_coefficients, features)) + data.polynomial_intercept
        return raw_height - float(getattr(data, "zero_height_offset_mm", 0.0))

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional, Protocol, Sequence

from src.engine.robot.height_measuring.area_grid_height_model import AreaGridHeightModel
from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.robot.height_measuring.piecewise_bilinear_height_model import (
    BOTTOM_LEFT_CENTER,
    BOTTOM_RIGHT_CENTER,
    MARKER_LABELS,
    PiecewiseBilinearHeightModel,
    TOP_LEFT_CENTER,
    TOP_RIGHT_CENTER,
)
from src.engine.vision.i_vision_service import IVisionService

_logger = logging.getLogger(__name__)

_DEFAULT_VELOCITY = 30
_DEFAULT_ACCELERATION = 10
_MAX_MARKER_DETECTION_ATTEMPTS = 50
_VERIFICATION_SETTLE_THRESHOLD_MM = 0.25
_VERIFICATION_SETTLE_THRESHOLD_DEG = 0.25
_VERIFICATION_SETTLE_TIMEOUT_S = 10.0
_VERIFICATION_SETTLE_DELAY_S = 0.05

class _IRobotService(Protocol):
    def get_current_position(self) -> list: ...
    def move_ptp(self, position, tool, user, velocity, acceleration, wait_to_reach=False) -> bool: ...
    def stop_motion(self) -> bool: ...
    def enable_safety_walls(self) -> bool: ...
    def disable_safety_walls(self) -> bool: ...
    def are_safety_walls_enabled(self): ...


class _IHeightService(Protocol):
    def is_calibrated(self) -> bool: ...
    def begin_measurement_session(self) -> None: ...
    def end_measurement_session(self) -> None: ...
    def measure_at(self, x: float, y: float, *, already_at_xy: bool = False) -> Optional[float]: ...
    def get_calibration_data(self): ...
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


class ArucoMarkerHeightMappingService:
    """Measure heights at detected ArUco marker positions using the current homography."""

    def __init__(
        self,
        vision_service: IVisionService,
        robot_service: _IRobotService,
        height_service: _IHeightService,
        robot_config: _IRobotConfig,
        calib_config: _ICalibConfig,
        transformer: ICoordinateTransformer,
        *,
        use_marker_centre: bool = False,
    ):
        self._vision_service = vision_service
        self._robot_service = robot_service
        self._height_service = height_service
        self._robot_config = robot_config
        self._calib_config = calib_config
        self._transformer = transformer
        self._use_marker_centre = use_marker_centre
        self._stop_event = threading.Event()
        self._marker_reference_points_px: dict[int, tuple[float, float]] = {}
        self._marker_reference_points_mm: dict[int, tuple[float, float]] = {}
        self._pending_safety_wall_restore = False

    def stop(self) -> None:
        self._stop_event.set()
        try:
            self._robot_service.stop_motion()
        except Exception:
            _logger.exception("Failed to stop robot motion during marker height mapping")

    def restore_pending_safety_walls(self) -> bool:
        if not self._pending_safety_wall_restore:
            return True
        try:
            restored = bool(self._robot_service.enable_safety_walls())
        except Exception:
            _logger.exception("Failed to restore pending safety walls")
            return False
        if restored:
            self._pending_safety_wall_restore = False
            _logger.info("Area grid height mapping: safety walls restored")
        else:
            _logger.warning("Area grid height mapping: failed to restore pending safety walls")
        return restored

    def is_ready(self) -> bool:
        if self._vision_service is None or self._robot_service is None:
            return False
        if self._height_service is None or not self._height_service.is_calibrated():
            return False
        if self._transformer is None:
            return False
        return self._is_homography_available()

    def measure_marker_heights(self) -> tuple[bool, str]:
        self._stop_event.clear()

        if self._vision_service is None:
            return False, "Vision service unavailable"
        if self._robot_service is None:
            return False, "Robot service unavailable"
        if self._height_service is None:
            return False, "Height measuring service unavailable"
        if not self._height_service.is_calibrated():
            return False, "Height measuring is not calibrated"
        if self._transformer is None:
            return False, "Homography transformer unavailable"

        self._transformer.reload()
        if not self._transformer.is_available():
            return False, "System not calibrated — run robot calibration first"

        measurement_pose = self._resolve_measurement_pose()
        if measurement_pose is None:
            return False, "Height measurement calibration pose is unavailable"

        self._height_service.begin_measurement_session()
        try:
            current_pos = self._robot_service.get_current_position()
            if not current_pos or len(current_pos) < 6:
                return False, "Failed to get current robot position"

            z_target, rx, ry, rz = measurement_pose
            tool = int(getattr(self._robot_config, "robot_tool", 0))
            user = int(getattr(self._robot_config, "robot_user", 0))
            velocity = int(getattr(self._calib_config, "velocity", _DEFAULT_VELOCITY))
            acceleration = int(getattr(self._calib_config, "acceleration", _DEFAULT_ACCELERATION))
            required_ids = [int(v) for v in getattr(self._calib_config, "required_ids", [])]
            required = set(required_ids) or None

            detected_by_id = self._collect_required_markers(required_ids)
            if detected_by_id is None:
                return False, "Failed to collect all required ArUco markers within 50 attempts"

            if required_ids:
                ordered_pairs = [
                    (
                        marker_id,
                        self._marker_reference_points_px[marker_id],
                        self._marker_reference_points_mm[marker_id],
                    )
                    for marker_id in required_ids
                ]
            else:
                ordered_pairs = sorted(
                    (
                        (marker_id, self._marker_reference_points_px[marker_id], self._marker_reference_points_mm[marker_id])
                        for marker_id in self._marker_reference_points_px
                    ),
                    key=lambda p: p[0],
                )
            ordered_pairs.extend(self._build_support_points())
            _logger.info(
                "Aruco marker height mapping started: tool=%d user=%d vel=%d acc=%d z=%.3f required=%s",
                tool,
                user,
                velocity,
                acceleration,
                z_target,
                required_ids or required,
            )

            return self._measure_points(
                ordered_pairs=ordered_pairs,
                z_target=z_target,
                rx=rx,
                ry=ry,
                rz=rz,
                tool=tool,
                user=user,
                velocity=velocity,
                acceleration=acceleration,
                save_ids=True,
                report_title="ArUco Marker Height Mapping Report",
                start_label="Aruco marker height mapping",
                success_label="Marker height mapping complete",
                strict_fail_on_unreachable=True,
                recovery_anchor_mm=self._marker_reference_points_mm.get(0),
            )
        finally:
            self._height_service.end_measurement_session()

    def generate_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> list[tuple[float, float]]:
        if rows < 2 or cols < 2:
            return []
        if len(corners_norm) != 4:
            return []
        corners = self._normalize_quad(corners_norm)
        return self._generate_grid_points(corners, rows, cols)

    def measure_area_grid(
        self,
        area_id: str,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
        support_points_mm: list[tuple[str, float, float]] | None = None,
        skip_labels: set[str] | None = None,
    ) -> tuple[bool, str]:
        self._stop_event.clear()

        if self._vision_service is None:
            return False, "Vision service unavailable"
        if self._robot_service is None:
            return False, "Robot service unavailable"
        if self._height_service is None:
            return False, "Height measuring service unavailable"
        if not self._height_service.is_calibrated():
            return False, "Height measuring is not calibrated"
        if self._transformer is None:
            return False, "Homography transformer unavailable"
        if rows < 2 or cols < 2:
            return False, "Grid rows and cols must both be at least 2"
        if len(corners_norm) != 4:
            return False, "Exactly 4 area corners are required"

        self._transformer.reload()
        if not self._transformer.is_available():
            return False, "System not calibrated — run robot calibration first"

        measurement_pose = self._resolve_measurement_pose()
        if measurement_pose is None:
            return False, "Height measurement calibration pose is unavailable"

        current_pos = self._robot_service.get_current_position()
        if not current_pos or len(current_pos) < 6:
            return False, "Failed to get current robot position"

        z_target, rx, ry, rz = measurement_pose
        tool = int(getattr(self._robot_config, "robot_tool", 0))
        user = int(getattr(self._robot_config, "robot_user", 0))
        velocity = int(getattr(self._calib_config, "velocity", _DEFAULT_VELOCITY))
        acceleration = int(getattr(self._calib_config, "acceleration", _DEFAULT_ACCELERATION))

        grid_norm = self.generate_area_grid(corners_norm, rows, cols)
        if not grid_norm:
            return False, "Failed to generate grid points from the selected area"

        width = float(self._vision_service.get_camera_width())
        height = float(self._vision_service.get_camera_height())
        ordered_pairs: list[tuple[object, tuple[float, float], tuple[float, float]]] = []
        for index, (xn, yn) in enumerate(grid_norm):
            row_idx = index // cols
            col_idx = index % cols
            px = xn * width
            py = yn * height
            ordered_pairs.append(
                (
                    f"r{row_idx + 1}c{col_idx + 1}",
                    (float(px), float(py)),
                    self._transformer.transform(float(px), float(py)),
                )
            )

        for sup_label, sx_mm, sy_mm in (support_points_mm or []):
            try:
                sup_px, sup_py = self._transformer.inverse_transform(float(sx_mm), float(sy_mm))
            except Exception:
                sup_px, sup_py = 0.0, 0.0
            ordered_pairs.append((sup_label, (float(sup_px), float(sup_py)), (float(sx_mm), float(sy_mm))))
            _logger.info("Support point %s added: x=%.3f y=%.3f mm", sup_label, sx_mm, sy_mm)

        # Pre-register known-unreachable labels so _measure_points never attempts them
        all_pairs = list(ordered_pairs)  # keep for planned_* metadata (includes skipped)
        pre_skipped: list[str] = []
        if skip_labels:
            filtered_pairs = []
            for pair in ordered_pairs:
                if str(pair[0]) in skip_labels:
                    pre_skipped.append(str(pair[0]))
                    _logger.info("Pre-skipping known-unreachable point %s", pair[0])
                else:
                    filtered_pairs.append(pair)
            ordered_pairs = filtered_pairs

        self._height_service.begin_measurement_session()
        safety_walls_enabled = self._robot_service.are_safety_walls_enabled()
        if safety_walls_enabled:
            if self._robot_service.disable_safety_walls():
                self._pending_safety_wall_restore = True
                _logger.info("Area grid height mapping: safety walls disabled for measurement run")
            else:
                _logger.warning("Area grid height mapping: failed to disable safety walls before run")
        try:
            _logger.info(
                "Area grid height mapping started: rows=%d cols=%d tool=%d user=%d vel=%d acc=%d z=%.3f",
                rows,
                cols,
                tool,
                user,
                velocity,
                acceleration,
                z_target,
            )
            return self._measure_points(
                ordered_pairs=ordered_pairs,
                z_target=z_target,
                rx=rx,
                ry=ry,
                rz=rz,
                tool=tool,
                user=user,
                velocity=velocity,
                acceleration=acceleration,
                save_ids=False,
                report_title="Area Grid Height Mapping Report",
                start_label="Area grid height mapping",
                success_label="Area grid height mapping complete",
                strict_fail_on_unreachable=False,
                save_area_id=area_id,
                recovery_anchor_mm=ordered_pairs[0][2] if ordered_pairs else None,
                point_labels=[str(point_id) for point_id, _, _ in ordered_pairs],
                grid_rows=rows,
                grid_cols=cols,
                planned_samples=[[float(x_mm), float(y_mm)] for _, _, (x_mm, y_mm) in all_pairs],
                planned_point_labels=[str(point_id) for point_id, _, _ in all_pairs],
                initial_unavailable_labels=pre_skipped or None,
            )
        finally:
            self._height_service.end_measurement_session()

    def verify_height_model(self, area_id: str = "") -> tuple[bool, str]:
        if self._height_service is None:
            return False, "Height measuring service unavailable"
        if not self._height_service.is_calibrated():
            return False, "Height measuring is not calibrated"

        data = self._height_service.get_depth_map_data(area_id)
        if data is None or not data.has_data():
            return False, "No saved height map data available"

        verification_points = self._build_verification_points(data)
        if len(verification_points) < 4:
            return False, "Height model is not ready for 4-point verification"

        calib = self._height_service.get_calibration_data()
        if calib is None or not getattr(calib, "robot_initial_position", None):
            return False, "Height measurement calibration pose is unavailable"

        ref = list(calib.robot_initial_position)
        z_target = float(ref[2])
        rx = float(ref[3])
        ry = float(ref[4])
        rz = float(ref[5])
        anchor_xy = self._resolve_verification_anchor(data)
        tool = int(getattr(self._robot_config, "robot_tool", 0))
        user = int(getattr(self._robot_config, "robot_user", 0))
        velocity = int(getattr(self._calib_config, "velocity", _DEFAULT_VELOCITY))
        acceleration = int(getattr(self._calib_config, "acceleration", _DEFAULT_ACCELERATION))

        self._stop_event.clear()
        rows: list[tuple[str, float, float, float, float, float]] = []
        failures = 0
        self._height_service.begin_measurement_session()
        try:
            for point in verification_points:
                if self._stop_event.is_set():
                    self._log_verification_report(rows, interrupted=True)
                    return True, f"Height model verification stopped — measured {len(rows)} point(s)"

                moved = self._move_to_marker_pose(
                    x_mm=float(point.x),
                    y_mm=float(point.y),
                    z_target=z_target,
                    rx=rx,
                    ry=ry,
                    rz=rz,
                    tool=tool,
                    user=user,
                    velocity=velocity,
                    acceleration=acceleration,
                )
                if not moved:
                    recovered = self._recover_to_anchor(
                        current_point_id=point.name,
                        anchor_mm=anchor_xy,
                        z_target=z_target,
                        rx=rx,
                        ry=ry,
                        rz=rz,
                        tool=tool,
                        user=user,
                        velocity=velocity,
                        acceleration=acceleration,
                    )
                    if recovered:
                        moved = self._move_to_marker_pose(
                            x_mm=float(point.x),
                            y_mm=float(point.y),
                            z_target=z_target,
                            rx=rx,
                            ry=ry,
                            rz=rz,
                            tool=tool,
                            user=user,
                            velocity=velocity,
                            acceleration=acceleration,
                        )

                if not moved:
                    measured = None
                else:
                    settled = self._wait_for_pose_settle(
                        target_position=[float(point.x), float(point.y), z_target, rx, ry, rz],
                    )
                    if not settled:
                        _logger.warning(
                            "Height model verification pose did not settle at %s (x=%.3f y=%.3f)",
                            point.name,
                            point.x,
                            point.y,
                        )
                        measured = None
                    else:
                        measured = self._height_service.measure_at(point.x, point.y, already_at_xy=True)
                if measured is None:
                    failures += 1
                    _logger.warning(
                        "Height model verification failed at %s (x=%.3f y=%.3f)",
                        point.name,
                        point.x,
                        point.y,
                    )
                    continue

                error = float(measured) - float(point.predicted_height)
                rows.append(
                    (
                        point.name,
                        getattr(point, "source", getattr(point, "patch_name", "")),
                        getattr(point, "interpolation_mode", "triangle"),
                        float(point.x),
                        float(point.y),
                        float(point.predicted_height),
                        float(measured),
                        error,
                    )
                )

            self._log_verification_report(rows, interrupted=False)
            if failures > 0:
                return False, f"Height model verification incomplete — {failures} point(s) failed"
            return True, f"Height model verification complete — measured {len(rows)} point(s)"
        finally:
            self._height_service.end_measurement_session()

    @staticmethod
    def _resolve_verification_anchor(data) -> tuple[float, float] | None:
        labels = [str(label) for label in getattr(data, "point_labels", [])]
        points = [list(point) for point in getattr(data, "points", [])]
        for wanted in ("r1c1", "0"):
            for label, point in zip(labels, points):
                if label == wanted and len(point) >= 2:
                    return float(point[0]), float(point[1])

        planned_labels = [str(label) for label in getattr(data, "planned_point_labels", [])]
        planned_points = [list(point) for point in getattr(data, "planned_points", [])]
        for wanted in ("r1c1", "0"):
            for label, point in zip(planned_labels, planned_points):
                if label == wanted and len(point) >= 2:
                    return float(point[0]), float(point[1])
        return None

    def _resolve_measurement_pose(self) -> tuple[float, float, float, float] | None:
        calib = self._height_service.get_calibration_data()
        if calib is None:
            return None
        ref = getattr(calib, "robot_initial_position", None)
        if ref is None or len(ref) < 6:
            return None
        return float(ref[2]), float(ref[3]), float(ref[4]), float(ref[5])

    def _measure_points(
        self,
        *,
        ordered_pairs: list[tuple[object, tuple[float, float], tuple[float, float]]],
        z_target: float,
        rx: float,
        ry: float,
        rz: float,
        tool: int,
        user: int,
        velocity: int,
        acceleration: int,
        save_ids: bool,
        report_title: str,
        start_label: str,
        success_label: str,
        strict_fail_on_unreachable: bool,
        save_area_id: str = "",
        recovery_anchor_mm: tuple[float, float] | None,
        point_labels: Optional[list[str]] = None,
        grid_rows: int = 0,
        grid_cols: int = 0,
        planned_samples: Optional[list[list[float]]] = None,
        planned_point_labels: Optional[list[str]] = None,
        initial_unavailable_labels: Optional[list[str]] = None,
    ) -> tuple[bool, str]:
        samples: list[list[float]] = []
        report_rows: list[tuple[object, float, float, float]] = []
        processed = 0
        unavailable_labels: list[str] = list(initial_unavailable_labels or [])
        unreachable = len(unavailable_labels)

        for point_id, point_px, point_mm in ordered_pairs:
            if self._stop_event.is_set():
                self._save_samples(
                    samples,
                    self._extract_int_ids(report_rows) if save_ids else None,
                    area_id=save_area_id,
                    point_labels=self._extract_labels(report_rows) if point_labels else None,
                    grid_rows=grid_rows,
                    grid_cols=grid_cols,
                    planned_points=planned_samples,
                    planned_point_labels=planned_point_labels,
                    unavailable_point_labels=unavailable_labels,
                )
                return True, (
                    f"{success_label} — measured {processed} point(s), "
                    f"unreached {unreachable} point(s) before stop"
                )

            x_mm, y_mm = point_mm
            label = self._describe_point(point_id)
            _logger.info(
                "%s point %s (%s) x_pixels=(%.3f, %.3f) -> robot (%.3f, %.3f). Moving to measurement pose...",
                start_label,
                point_id,
                label,
                point_px[0],
                point_px[1],
                x_mm,
                y_mm,
            )

            ok = self._move_to_marker_pose(
                x_mm=x_mm,
                y_mm=y_mm,
                z_target=z_target,
                rx=rx,
                ry=ry,
                rz=rz,
                tool=tool,
                user=user,
                velocity=velocity,
                acceleration=acceleration,
            )
            if not ok:
                recovered = self._recover_to_anchor(
                    current_point_id=point_id,
                    anchor_mm=recovery_anchor_mm,
                    z_target=z_target,
                    rx=rx,
                    ry=ry,
                    rz=rz,
                    tool=tool,
                    user=user,
                    velocity=velocity,
                    acceleration=acceleration,
                )
                if recovered:
                    ok = self._move_to_marker_pose(
                        x_mm=x_mm,
                        y_mm=y_mm,
                        z_target=z_target,
                        rx=rx,
                        ry=ry,
                        rz=rz,
                        tool=tool,
                        user=user,
                        velocity=velocity,
                        acceleration=acceleration,
                    )

                if not ok:
                    unreachable += 1
                    unavailable_labels.append(str(point_id))
                    if strict_fail_on_unreachable:
                        self._save_samples(
                            samples,
                            self._extract_int_ids(report_rows) if save_ids else None,
                            area_id=save_area_id,
                            point_labels=self._extract_labels(report_rows) if point_labels else None,
                            grid_rows=grid_rows,
                            grid_cols=grid_cols,
                            planned_points=planned_samples,
                            planned_point_labels=planned_point_labels,
                            unavailable_point_labels=unavailable_labels,
                        )
                        if recovered:
                            return False, f"Move to point {point_id} failed after recovery retry"
                        return False, f"Move to point {point_id} failed"
                    _logger.warning(
                        "Skipping unreachable point %s (%s); reached=%d unreached=%d",
                        point_id,
                        label,
                        processed,
                        unreachable,
                    )
                    continue

            if self._stop_event.is_set():
                self._save_samples(
                    samples,
                    self._extract_int_ids(report_rows) if save_ids else None,
                    area_id=save_area_id,
                    point_labels=self._extract_labels(report_rows) if point_labels else None,
                    grid_rows=grid_rows,
                    grid_cols=grid_cols,
                    planned_points=planned_samples,
                    planned_point_labels=planned_point_labels,
                    unavailable_point_labels=unavailable_labels,
                )
                return True, (
                    f"{success_label} — measured {processed} point(s), "
                    f"unreached {unreachable} point(s) before stop"
                )

            settled = self._wait_for_pose_settle(
                target_position=[float(x_mm), float(y_mm), float(z_target), float(rx), float(ry), float(rz)],
            )
            if not settled:
                _logger.warning(
                    "Measurement pose did not settle for point %s (%s) at x=%.3f y=%.3f",
                    point_id,
                    label,
                    x_mm,
                    y_mm,
                )
                if strict_fail_on_unreachable:
                    self._save_samples(
                        samples,
                        self._extract_int_ids(report_rows) if save_ids else None,
                        area_id=save_area_id,
                        point_labels=self._extract_labels(report_rows) if point_labels else None,
                        grid_rows=grid_rows,
                        grid_cols=grid_cols,
                        planned_points=planned_samples,
                        planned_point_labels=planned_point_labels,
                        unavailable_point_labels=unavailable_labels,
                    )
                    return False, f"Point {point_id} did not settle at the measurement pose"
                unreachable += 1
                unavailable_labels.append(str(point_id))
                _logger.warning(
                    "Skipping unsettled point %s (%s); reached=%d unreached=%d",
                    point_id,
                    label,
                    processed,
                    unreachable,
                )
                continue

            height_mm = self._height_service.measure_at(x_mm, y_mm, already_at_xy=True)
            if height_mm is None:
                _logger.warning("Height measurement failed for point %s (%s)", point_id, label)
                continue

            measured_pose = self._robot_service.get_current_position()
            sample_x = float(measured_pose[0]) if measured_pose and len(measured_pose) >= 2 else float(x_mm)
            sample_y = float(measured_pose[1]) if measured_pose and len(measured_pose) >= 2 else float(y_mm)
            samples.append([sample_x, sample_y, float(height_mm)])
            report_rows.append((point_id, sample_x, sample_y, float(height_mm)))
            processed += 1
            _logger.info(
                "Stored point %s (%s) sample #%d: x=%.3f y=%.3f h=%.4f",
                point_id,
                label,
                processed,
                sample_x,
                sample_y,
                float(height_mm),
            )

        self._save_samples(
            samples,
            self._extract_int_ids(report_rows) if save_ids else None,
            area_id=save_area_id,
            point_labels=self._extract_labels(report_rows) if point_labels else None,
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            planned_points=planned_samples,
            planned_point_labels=planned_point_labels,
            unavailable_point_labels=unavailable_labels,
        )
        if processed == 0:
            return False, "No point heights were measured"
        self._log_final_report(
            report_rows,
            title=report_title,
            unreachable_count=unreachable,
            unavailable_labels=unavailable_labels,
        )
        return True, f"{success_label} — measured {processed} point(s), unreached {unreachable} point(s)"

    @staticmethod
    def _extract_int_ids(report_rows: list[tuple[object, float, float, float]]) -> list[int]:
        ids: list[int] = []
        for point_id, _, _, _ in report_rows:
            if isinstance(point_id, int):
                ids.append(point_id)
        return ids

    @staticmethod
    def _extract_labels(report_rows: list[tuple[object, float, float, float]]) -> list[str]:
        return [str(point_id) for point_id, _, _, _ in report_rows]

    @staticmethod
    def _describe_point(point_id: object) -> str:
        if isinstance(point_id, int):
            return MARKER_LABELS.get(point_id, "support point")
        return str(point_id)

    @staticmethod
    def _normalize_quad(corners_norm: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
        points = [(float(x), float(y)) for x, y in corners_norm[:4]]
        tl = min(points, key=lambda point: point[0] + point[1])
        br = max(points, key=lambda point: point[0] + point[1])
        tr = min(points, key=lambda point: point[1] - point[0])
        bl = max(points, key=lambda point: point[1] - point[0])
        return [tl, tr, br, bl]

    @staticmethod
    def _generate_grid_points(
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> list[tuple[float, float]]:
        tl, tr, br, bl = corners_norm
        points: list[tuple[float, float]] = []
        for row_idx in range(rows):
            v = row_idx / float(rows - 1) if rows > 1 else 0.0
            for col_idx in range(cols):
                u = col_idx / float(cols - 1) if cols > 1 else 0.0
                x = (
                    (1.0 - u) * (1.0 - v) * tl[0]
                    + u * (1.0 - v) * tr[0]
                    + u * v * br[0]
                    + (1.0 - u) * v * bl[0]
                )
                y = (
                    (1.0 - u) * (1.0 - v) * tl[1]
                    + u * (1.0 - v) * tr[1]
                    + u * v * br[1]
                    + (1.0 - u) * v * bl[1]
                )
                points.append((float(x), float(y)))
        return points

    def _save_samples(
        self,
        samples: list[list[float]],
        point_ids: Optional[list[int]] = None,
        *,
        area_id: str = "",
        point_labels: Optional[list[str]] = None,
        grid_rows: int = 0,
        grid_cols: int = 0,
        planned_points: Optional[list[list[float]]] = None,
        planned_point_labels: Optional[list[str]] = None,
        unavailable_point_labels: Optional[list[str]] = None,
    ) -> None:
        if not samples:
            return
        try:
            self._height_service.save_height_map(
                samples,
                area_id=area_id,
                marker_ids=point_ids,
                point_labels=point_labels,
                grid_rows=grid_rows,
                grid_cols=grid_cols,
                planned_points=planned_points,
                planned_point_labels=planned_point_labels,
                unavailable_point_labels=unavailable_point_labels,
            )
        except Exception:
            _logger.exception("Failed to save measured marker height map")

    def _build_verification_points(self, data) -> list[object]:
        model = PiecewiseBilinearHeightModel.from_depth_map(data)
        verification_points = model.verification_points()
        if verification_points:
            return verification_points
        return AreaGridHeightModel.from_depth_map(data).verification_points()

    def _log_final_report(
        self,
        report_rows: list[tuple[object, float, float, float]],
        *,
        title: str,
        unreachable_count: int = 0,
        unavailable_labels: Optional[list[str]] = None,
    ) -> None:
        if not report_rows:
            return

        lines = [
            "",
            f"=== {title} ===",
        ]
        for point_id, x_mm, y_mm, height_mm in report_rows:
            label = MARKER_LABELS.get(point_id) if isinstance(point_id, int) else None
            suffix = f" ({label})" if label else ""
            lines.append(f"[{point_id}] x={x_mm:.3f} y={y_mm:.3f} height={height_mm:.4f} mm{suffix}")
        for label in unavailable_labels or []:
            lines.append(f"[{label}] data=N/A")
        lines.append(f"Reached points: {len(report_rows)}")
        lines.append(f"Unreached points: {int(unreachable_count)}")
        lines.append(f"Total planned points: {len(report_rows) + int(unreachable_count)}")
        lines.append("=========================================")
        _logger.info("\n".join(lines))

    def _log_verification_report(
        self,
        rows: list[tuple[str, str, str, float, float, float, float, float]],
        *,
        interrupted: bool,
    ) -> None:
        if not rows:
            return

        abs_errors = [abs(row[7]) for row in rows]
        lines = [
            "",
            "=== Height Model Verification Report ===",
        ]
        for name, source, interpolation_mode, x_mm, y_mm, predicted, measured, error in rows:
            lines.append(
                f"{name}: source={source} mode={interpolation_mode} "
                f"x={x_mm:.3f} y={y_mm:.3f} predicted={predicted:.4f} mm "
                f"measured={measured:.4f} mm error={error:+.4f} mm"
            )
        lines.append(f"Mean abs error: {sum(abs_errors) / len(abs_errors):.4f} mm")
        lines.append(f"Max abs error: {max(abs_errors):.4f} mm")
        if interrupted:
            lines.append("Verification interrupted before all planned points were measured")
        lines.append("========================================")
        _logger.info("\n".join(lines))

    def _move_to_marker_pose(
        self,
        *,
        x_mm: float,
        y_mm: float,
        z_target: float,
        rx: float,
        ry: float,
        rz: float,
        tool: int,
        user: int,
        velocity: int,
        acceleration: int,
        ) -> bool:
        return self._robot_service.move_ptp(
            position=[x_mm, y_mm, z_target, rx, ry, rz],
            tool=tool,
            user=user,
            velocity=velocity,
            acceleration=acceleration,
            wait_to_reach=True,
        )

    def _wait_for_pose_settle(self, *, target_position: list[float]) -> bool:
        deadline = time.time() + _VERIFICATION_SETTLE_TIMEOUT_S
        last_current = None
        while time.time() < deadline:
            current = self._robot_service.get_current_position()
            last_current = current
            if current and len(current) >= 6:
                pos_ok = (
                        abs(float(current[0]) - float(target_position[0])) <= _VERIFICATION_SETTLE_THRESHOLD_MM
                        and abs(float(current[1]) - float(target_position[1])) <= _VERIFICATION_SETTLE_THRESHOLD_MM
                        and abs(float(current[2]) - float(target_position[2])) <= _VERIFICATION_SETTLE_THRESHOLD_MM
                )
                ang_ok = (
                        self._angle_diff(float(current[3]),
                                         float(target_position[3])) <= _VERIFICATION_SETTLE_THRESHOLD_DEG
                        and self._angle_diff(float(current[4]),
                                             float(target_position[4])) <= _VERIFICATION_SETTLE_THRESHOLD_DEG
                        and self._angle_diff(float(current[5]),
                                             float(target_position[5])) <= _VERIFICATION_SETTLE_THRESHOLD_DEG
                )

                if pos_ok and ang_ok:
                    return True
            if self._stop_event.is_set():
                return False
            time.sleep(_VERIFICATION_SETTLE_DELAY_S)
        _logger.warning(
            f"Pose did not settle target->{target_position} , current->{last_current} within {int(_VERIFICATION_SETTLE_TIMEOUT_S)}s")
        return False

    @staticmethod
    def _angle_diff(a: float, b: float) -> float:
        d = (a - b) % 360.0
        if d > 180.0:
            d -= 360.0
        return abs(d)

    def _recover_via_marker_zero(
        self,
        *,
        current_marker_id: int,
        z_target: float,
        rx: float,
        ry: float,
        rz: float,
        tool: int,
        user: int,
        velocity: int,
        acceleration: int,
    ) -> bool:
        marker_zero = self._marker_reference_points_mm.get(0)
        if marker_zero is None or current_marker_id == 0:
            _logger.error(
                "Move to marker %d failed and marker-0 recovery is unavailable",
                current_marker_id,
            )
            return False

        _logger.warning(
            "Move to marker %d failed; moving to marker 0 and retrying",
            current_marker_id,
        )
        ok = self._move_to_marker_pose(
            x_mm=marker_zero[0],
            y_mm=marker_zero[1],
            z_target=z_target,
            rx=rx,
            ry=ry,
            rz=rz,
            tool=tool,
            user=user,
            velocity=velocity,
            acceleration=acceleration,
        )
        if not ok:
            _logger.error("Marker-0 recovery move failed")
            return False
        return True

    def _recover_to_anchor(
        self,
        *,
        current_point_id: object,
        anchor_mm: tuple[float, float] | None,
        z_target: float,
        rx: float,
        ry: float,
        rz: float,
        tool: int,
        user: int,
        velocity: int,
        acceleration: int,
    ) -> bool:
        if anchor_mm is None:
            return False

        if current_point_id == 0 or current_point_id == "r1c1":
            return False

        _logger.warning(
            "Move to point %s failed; moving to recovery anchor and retrying once",
            current_point_id,
        )
        ok = self._move_to_marker_pose(
            x_mm=anchor_mm[0],
            y_mm=anchor_mm[1],
            z_target=z_target,
            rx=rx,
            ry=ry,
            rz=rz,
            tool=tool,
            user=user,
            velocity=velocity,
            acceleration=acceleration,
        )
        if not ok:
            _logger.error("Recovery anchor move failed")
            return False
        return True

    def _build_support_points(self) -> list[tuple[int, tuple[float, float], tuple[float, float]]]:
        required = {0, 1, 2, 3, 4, 5, 6, 8}
        if not required.issubset(self._marker_reference_points_mm):
            return []

        missing_px = self._infer_missing_bottom_mid(self._marker_reference_points_px)
        missing_mm = self._infer_missing_bottom_mid(self._marker_reference_points_mm)

        return [
            (
                TOP_LEFT_CENTER,
                self._average_points_px(0, 1, 3, 4),
                self._average_points_mm(0, 1, 3, 4),
            ),
            (
                TOP_RIGHT_CENTER,
                self._average_points_px(1, 2, 4, 5),
                self._average_points_mm(1, 2, 4, 5),
            ),
            (
                BOTTOM_LEFT_CENTER,
                self._average_points(
                    self._marker_reference_points_px[3],
                    self._marker_reference_points_px[4],
                    self._marker_reference_points_px[6],
                    missing_px,
                ),
                self._average_points(
                    self._marker_reference_points_mm[3],
                    self._marker_reference_points_mm[4],
                    self._marker_reference_points_mm[6],
                    missing_mm,
                ),
            ),
            (
                BOTTOM_RIGHT_CENTER,
                self._average_points(
                    self._marker_reference_points_px[4],
                    self._marker_reference_points_px[5],
                    missing_px,
                    self._marker_reference_points_px[8],
                ),
                self._average_points(
                    self._marker_reference_points_mm[4],
                    self._marker_reference_points_mm[5],
                    missing_mm,
                    self._marker_reference_points_mm[8],
                ),
            ),
        ]

    def _average_points_px(self, *point_ids: int) -> tuple[float, float]:
        return self._average_points(*(self._marker_reference_points_px[point_id] for point_id in point_ids))

    def _average_points_mm(self, *point_ids: int) -> tuple[float, float]:
        return self._average_points(*(self._marker_reference_points_mm[point_id] for point_id in point_ids))

    @staticmethod
    def _average_points(*points: tuple[float, float]) -> tuple[float, float]:
        count = float(len(points))
        return (
            sum(float(point[0]) for point in points) / count,
            sum(float(point[1]) for point in points) / count,
        )

    @staticmethod
    def _infer_missing_bottom_mid(points: dict[int, tuple[float, float]]) -> tuple[float, float]:
        p3 = points[3]
        p4 = points[4]
        p5 = points[5]
        p6 = points[6]
        p8 = points[8]
        candidates = [
            (p6[0] + (p4[0] - p3[0]), p6[1] + (p4[1] - p3[1])),
            (p8[0] + (p4[0] - p5[0]), p8[1] + (p4[1] - p5[1])),
            (p4[0] + (p6[0] - p3[0]), p4[1] + (p6[1] - p3[1])),
            (p4[0] + (p8[0] - p5[0]), p4[1] + (p8[1] - p5[1])),
        ]
        return ArucoMarkerHeightMappingService._average_points(*candidates)

    def _collect_required_markers(self, required_ids: list[int]) -> Optional[dict[int, object]]:
        detected_by_id: dict[int, object] = {}
        attempts = 0

        while attempts < _MAX_MARKER_DETECTION_ATTEMPTS:
            if self._stop_event.is_set():
                return None

            frame = self._vision_service.get_latest_frame()
            if frame is None:
                attempts += 1
                time.sleep(0.1)
                continue

            corners, ids, _ = self._vision_service.detect_aruco_markers(frame)
            attempts += 1
            if ids is None or len(ids) == 0:
                time.sleep(0.1)
                continue

            for marker_id, marker_corners in zip(ids.flatten(), corners):
                detected_by_id[int(marker_id)] = marker_corners

            if required_ids:
                missing = [marker_id for marker_id in required_ids if marker_id not in detected_by_id]
                if not missing:
                    break
                _logger.debug(
                    "Marker height mapping attempt %d/%d: still missing required markers %s",
                    attempts,
                    _MAX_MARKER_DETECTION_ATTEMPTS,
                    missing,
                )
            else:
                break

            time.sleep(0.1)

        if required_ids and any(marker_id not in detected_by_id for marker_id in required_ids):
            return None

        self._marker_reference_points_px = {}
        self._marker_reference_points_mm = {}
        for marker_id, marker_corners in detected_by_id.items():
            corners_4 = marker_corners[0]
            if self._use_marker_centre:
                ref_pt = corners_4.mean(axis=0)
            else:
                ref_pt = corners_4[0]
            px_pt = (float(ref_pt[0]), float(ref_pt[1]))
            self._marker_reference_points_px[marker_id] = px_pt
            self._marker_reference_points_mm[marker_id] = self._transformer.transform(px_pt[0], px_pt[1])
        return detected_by_id

    def _is_homography_available(self) -> bool:
        robot_matrix = self._vision_service.camera_to_robot_matrix_path
        storage_dir = os.path.dirname(robot_matrix)
        camera_matrix = os.path.join(storage_dir, "camera_calibration.npz")
        return os.path.isfile(robot_matrix) and os.path.isfile(camera_matrix)

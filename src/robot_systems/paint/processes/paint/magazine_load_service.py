from __future__ import annotations

import logging
import math
from time import monotonic, sleep
from typing import Callable

import cv2
import numpy as np

from src.engine.robot.path_preparation.geometry import compute_pickup_rz_from_min_rect_long_axis
from src.engine.robot.motion_sequence import OrderedMotionType
from src.engine.robot.targeting.vision_pose_request import VisionPoseRequest
from src.robot_systems.paint.processes.paint.config import PaintMagazineLoadConfig
from src.robot_systems.paint.processes.paint.motion.pose_sampling import (
    FreshPoseReadError,
    read_fresh_pose,
)
from src.robot_systems.paint.processes.paint.work_area_nesting import WorkAreaNestingService

_logger = logging.getLogger(__name__)


class PaintMagazineLoadService:
    """Move a workpiece from the magazine capture station to calibration before painting."""

    def __init__(
        self,
        *,
        navigation,
        capture_snapshot_service,
        path_executor,
        resolver_getter=None,
        work_area_service=None,
        release_image_size_getter=None,
        target_point_name: str = "tool",
        camera_point_name: str = "camera",
        frame_name: str = "magazine",
        release_work_area_id: str = "paint",
        release_frame_name: str = "calibration",
    ) -> None:
        self._navigation = navigation
        self._capture_snapshot_service = capture_snapshot_service
        self._path_executor = path_executor
        self._resolver_getter = resolver_getter
        self._work_area_service = work_area_service
        self._release_image_size_getter = release_image_size_getter
        self._target_point_name = str(target_point_name or "tool").strip().lower()
        self._camera_point_name = str(camera_point_name or "camera").strip().lower()
        self._frame_name = str(frame_name or "magazine").strip().lower()
        self._release_work_area_id = str(release_work_area_id or "paint").strip().lower()
        self._release_frame_name = str(release_frame_name or "calibration").strip().lower()
        self._work_area_nesting = WorkAreaNestingService()

    def clear_work_area_nesting(self) -> None:
        self._work_area_nesting.clear()

    def commit_work_area_nesting(self) -> None:
        self._work_area_nesting.commit()

    def cancel_work_area_nesting(self) -> None:
        self._work_area_nesting.cancel()

    def _resolve_auto_discovery_approach_pose(
        self,
        contour,
        magazine_group: str,
        config: PaintMagazineLoadConfig,
    ) -> list[float] | None:
        """Resolve the safe vertical approach pose for an already-captured pile."""
        if contour is None:
            return None
        magazine_pose = self._navigation.get_group_position(magazine_group)
        if magazine_pose is None or len(magazine_pose) < 6:
            return None
        target = self._resolve_pickup_target(contour, magazine_pose)
        if target is None:
            return None
        pickup_xy = target.get("pickup_xy")
        if pickup_xy is None or len(pickup_xy) < 2:
            return None
        return [
            float(pickup_xy[0]),
            float(pickup_xy[1]),
            float(config.full_retract_z_mm),
            float(magazine_pose[3]),
            float(magazine_pose[4]),
            float(target["pickup_rz"]),
        ]

    def _move_to_group_with_pause_resume_recovery(
        self,
        context: object,
        state,
        group_name: str,
        *,
        velocity: float,
        acceleration: float,
        motion_type: OrderedMotionType,
        blendR: float | None = None,
    ) -> bool:
        ok = self._navigation.move_to_group(
            group_name,
            wait_cancelled=context.motion_cancel_requested,
            velocity=velocity,
            acceleration=acceleration,
            motion_type=motion_type,
            blendR=blendR,
        )
        if ok:
            context.resume_retry_available = False
        return ok

    def _move_to_pose_with_pause_resume_recovery(
        self,
        context: object,
        state,
        pose: list[float],
        group_name: str,
        *,
        velocity: float,
        acceleration: float,
        motion_type: OrderedMotionType,
        blendR: float | None = None,
    ) -> bool:
        return self._navigation.move_to_position(
            pose,
            group_name,
            wait_cancelled=context.motion_cancel_requested,
            velocity=velocity,
            acceleration=acceleration,
            motion_type=motion_type,
            blendR=blendR,
        )

    def _mark_magazine_capture_area_active(self) -> None:
        if self._work_area_service is None:
            return
        self._work_area_service.set_active_area_id(self._frame_name)
        self._work_area_service.mark_active_area_verified(self._frame_name)

    def _resolve_work_area_center_release_pose(
        self,
        *,
        base_pose: list[float],
        frame,
        release_z_mm: float,
    ) -> list[float] | None:
        started = monotonic()
        if len(base_pose) < 6:
            return None
        center_started = monotonic()
        center_px = self._release_work_area_center_px(frame)
        center_elapsed = monotonic() - center_started
        if center_px is None:
            return None
        resolver_started = monotonic()
        resolver = self._resolver()
        resolver_elapsed = monotonic() - resolver_started
        if resolver is None:
            return None
        registry_started = monotonic()
        target_point = resolver.registry.by_name(self._target_point_name)
        registry_elapsed = monotonic() - registry_started
        resolve_started = monotonic()
        result = resolver.resolve(
            VisionPoseRequest(
                x_pixels=float(center_px[0]),
                y_pixels=float(center_px[1]),
                z_mm=float(release_z_mm),
                rx_degrees=float(base_pose[3]),
                ry_degrees=float(base_pose[4]),
                rz_degrees=float(base_pose[5]),
            ),
            target_point,
            frame=self._release_frame_name,
        )
        resolve_elapsed = monotonic() - resolve_started
        release_pose = list(base_pose)
        release_pose[0] = float(result.final_xy[0])
        release_pose[1] = float(result.final_xy[1])
        release_pose[2] = float(release_z_mm)
        _logger.info(
            "[MAGAZINE_LOAD] release target work_area=%s frame=%s center_px=(%.3f, %.3f) "
            "release_xyz=(%.3f, %.3f, %.3f)",
            self._release_work_area_id,
            self._release_frame_name,
            float(center_px[0]),
            float(center_px[1]),
            float(release_pose[0]),
            float(release_pose[1]),
            float(release_pose[2]),
        )
        _logger.debug(
            "[MAGAZINE_LOAD_TIMING] release_pose center_px_s=%.3f resolver_s=%.3f registry_s=%.3f "
            "resolve_s=%.3f total_s=%.3f",
            center_elapsed,
            resolver_elapsed,
            registry_elapsed,
            resolve_elapsed,
            monotonic() - started,
        )
        return release_pose

    def _resolve_nested_work_area_release_pose(
        self,
        *,
        base_pose: list[float],
        frame,
        release_z_mm: float,
        robot_contour_xy,
        margin_mm: float,
        padding_mm: float,
    ) -> tuple[list[float] | None, bool, str]:
        image_size = self._release_image_size(frame)
        points = (
            self._work_area_service.get_work_area(self._release_work_area_id)
            if self._work_area_service is not None
            else None
        )
        resolver = self._resolver()
        if image_size is None or points is None or len(points) == 0 or resolver is None or len(base_pose) < 6:
            return None, False, "Batch nesting could not resolve the paint work area"
        width_px, height_px = image_size
        target_point = resolver.registry.by_name(self._target_point_name)
        boundary_xy = []
        for normalized_x, normalized_y in points:
            result = resolver.resolve(
                VisionPoseRequest(
                    x_pixels=float(normalized_x) * float(width_px),
                    y_pixels=float(normalized_y) * float(height_px),
                    z_mm=float(release_z_mm),
                    rx_degrees=float(base_pose[3]),
                    ry_degrees=float(base_pose[4]),
                    rz_degrees=float(base_pose[5]),
                ),
                target_point,
                frame=self._release_frame_name,
            )
            boundary_xy.append((float(result.final_xy[0]), float(result.final_xy[1])))
        contour = np.asarray(robot_contour_xy, dtype=np.float64).reshape(-1, 2)
        if len(contour) < 3:
            return None, False, "Batch nesting could not determine the workpiece footprint"
        (_center, dimensions, _angle) = cv2.minAreaRect(contour.astype(np.float32))
        # A square based on the longest side is conservative for every release
        # orientation and prevents rotated workpieces from violating padding.
        footprint = max(float(dimensions[0]), float(dimensions[1]))
        reservation, message = self._work_area_nesting.reserve(
            boundary_xy,
            width_mm=footprint,
            height_mm=footprint,
            margin_mm=float(margin_mm),
            padding_mm=float(padding_mm),
        )
        if reservation is None:
            return None, False, message
        release_pose = list(base_pose[:6])
        release_pose[0], release_pose[1] = reservation.center_xy
        release_pose[2] = float(release_z_mm)
        _logger.info(
            "[BATCH_NESTING] reserved release_xy=(%.3f, %.3f) footprint_mm=%.3f has_more=%s",
            release_pose[0], release_pose[1], footprint,
            reservation.has_space_for_same_footprint,
        )
        return release_pose, reservation.has_space_for_same_footprint, ""

    def _release_work_area_center_px(self, frame) -> tuple[float, float] | None:
        started = monotonic()
        if self._work_area_service is None:
            return None
        image_size = self._release_image_size(frame)
        if image_size is None:
            return None
        width, height = image_size
        if not width or not height:
            return None
        points = self._work_area_service.get_work_area(self._release_work_area_id)
        if not points:
            return None
        try:
            arr = np.asarray(points, dtype=np.float64).reshape(-1, 2)
        except ValueError:
            return None
        if len(arr) < 3:
            return None
        points_px = np.column_stack((arr[:, 0] * float(width), arr[:, 1] * float(height)))
        center = _contour_center_px(points_px)
        _logger.debug(
            "[MAGAZINE_LOAD_TIMING] release_work_area_center_px total_s=%.3f points=%d frame_size=%dx%d",
            monotonic() - started,
            len(points_px),
            int(width),
            int(height),
        )
        return center

    def _release_image_size(self, frame) -> tuple[int, int] | None:
        if frame is not None and hasattr(frame, "shape"):
            try:
                height, width = frame.shape[:2]
                if int(width) > 0 and int(height) > 0:
                    return int(width), int(height)
            except (TypeError, ValueError):
                pass
        getter = self._release_image_size_getter
        if not callable(getter):
            return None
        try:
            width, height = getter()
            width = int(width)
            height = int(height)
        except (TypeError, ValueError, AttributeError):
            _logger.exception("[MAGAZINE_LOAD] Failed to read configured release image size")
            return None
        return (width, height) if width > 0 and height > 0 else None

    def _resolve_pickup_target(self, contour, magazine_pose: list[float]) -> dict | None:
        started = monotonic()
        points_started = monotonic()
        points_px = _contour_points_array(contour)
        points_elapsed = monotonic() - points_started
        if len(points_px) < 3 or len(magazine_pose) < 6:
            return None
        center_started = monotonic()
        center_px = _contour_center_px(points_px)
        center_elapsed = monotonic() - center_started
        if center_px is None:
            return None
        resolver_started = monotonic()
        resolver = self._resolver()
        resolver_elapsed = monotonic() - resolver_started
        if resolver is None:
            return None
        registry_started = monotonic()
        camera_point = resolver.registry.by_name(self._camera_point_name)
        target_point = resolver.registry.by_name(self._target_point_name)
        registry_elapsed = monotonic() - registry_started
        reference_rz = float(magazine_pose[5])
        rx = float(magazine_pose[3])
        ry = float(magazine_pose[4])
        z = float(magazine_pose[2])
        frame_obj = resolver.get_frame(self._frame_name)
        mapper = frame_obj.mapper
        if mapper is None:
            _logger.warning(
                "[MAGAZINE_TARGET_DIAGNOSTIC] frame=%s has no plane mapper; "
                "capture_pose=(%.3f, %.3f, %.3f, %.3f, %.3f, %.3f)",
                self._frame_name,
                *(float(value) for value in magazine_pose[:6]),
            )
        else:
            source_pose = mapper.source_pose
            target_pose = mapper.target_pose
            _logger.info(
                "[MAGAZINE_TARGET_DIAGNOSTIC] frame=%s "
                "capture_pose=(%.3f, %.3f, %.3f, %.3f, %.3f, %.3f) "
                "configured_source_xy_rz=(%.3f, %.3f, %.3f) "
                "configured_target_xy_rz=(%.3f, %.3f, %.3f) "
                "configured_delta_xy_rz=(%.3f, %.3f, %.3f) "
                "capture_minus_configured_target_xy_rz=(%.3f, %.3f, %.3f)",
                self._frame_name,
                *(float(value) for value in magazine_pose[:6]),
                float(source_pose.x),
                float(source_pose.y),
                float(source_pose.rz),
                float(target_pose.x),
                float(target_pose.y),
                float(target_pose.rz),
                float(target_pose.x - source_pose.x),
                float(target_pose.y - source_pose.y),
                float(target_pose.rz - source_pose.rz),
                float(magazine_pose[0] - target_pose.x),
                float(magazine_pose[1] - target_pose.y),
                float(magazine_pose[5] - target_pose.rz),
            )
        robot_contour_xy = []
        contour_resolve_started = monotonic()
        for px, py in points_px:
            result = resolver.resolve(
                VisionPoseRequest(
                    x_pixels=float(px),
                    y_pixels=float(py),
                    z_mm=z,
                    rx_degrees=rx,
                    ry_degrees=ry,
                    rz_degrees=reference_rz,
                ),
                camera_point,
                frame=self._frame_name,
            )
            robot_contour_xy.append([float(result.final_xy[0]), float(result.final_xy[1])])
        contour_resolve_elapsed = monotonic() - contour_resolve_started
        rz_started = monotonic()
        pickup_rz = compute_pickup_rz_from_min_rect_long_axis(robot_contour_xy, reference_rz)
        rz_elapsed = monotonic() - rz_started
        center_resolve_started = monotonic()
        center_result = resolver.resolve(
            VisionPoseRequest(
                x_pixels=float(center_px[0]),
                y_pixels=float(center_px[1]),
                z_mm=z,
                rx_degrees=rx,
                ry_degrees=ry,
                rz_degrees=float(pickup_rz),
            ),
            target_point,
            frame=self._frame_name,
        )
        center_resolve_elapsed = monotonic() - center_resolve_started
        diagnostic_calibration_xy = center_result.calibration_xy
        diagnostic_plane_xy = center_result.plane_xy
        diagnostic_tcp_delta = center_result.pickup_plane_reference_delta_xy
        diagnostic_target_delta = center_result.target_delta_xy
        _logger.debug(
            "[MAGAZINE_TARGET_DIAGNOSTIC] center_px=(%.3f, %.3f) point=%s "
            "homography_residual_xy=(%.3f, %.3f) mapped_plane_xy=(%.3f, %.3f) "
            "plane_delta_xy=(%.3f, %.3f) tcp_rotation_delta_xy=(%.3f, %.3f) "
            "target_point_delta_xy=(%.3f, %.3f) final_command_xy=(%.3f, %.3f) "
            "requested_rz=%.3f reference_rz=%.3f",
            float(center_px[0]),
            float(center_px[1]),
            str(target_point.name),
            float(diagnostic_calibration_xy[0]),
            float(diagnostic_calibration_xy[1]),
            float(diagnostic_plane_xy[0]),
            float(diagnostic_plane_xy[1]),
            float(diagnostic_plane_xy[0] - diagnostic_calibration_xy[0]),
            float(diagnostic_plane_xy[1] - diagnostic_calibration_xy[1]),
            float(diagnostic_tcp_delta[0]),
            float(diagnostic_tcp_delta[1]),
            float(diagnostic_target_delta[0]),
            float(diagnostic_target_delta[1]),
            float(center_result.final_xy[0]),
            float(center_result.final_xy[1]),
            float(pickup_rz),
            float(center_result.reference_rz),
        )
        _logger.info(
            "[MAGAZINE_LOAD] simple pickup target center_px=(%.3f, %.3f) pickup_xy=(%.3f, %.3f) pickup_rz=%.3f contour_points=%d",
            float(center_px[0]),
            float(center_px[1]),
            float(center_result.final_xy[0]),
            float(center_result.final_xy[1]),
            float(pickup_rz),
            len(points_px),
        )
        _logger.debug(
            "[MAGAZINE_LOAD_TIMING] pickup_target points_array_s=%.3f center_px_s=%.3f resolver_s=%.3f "
            "registry_s=%.3f contour_resolve_s=%.3f contour_points=%d avg_point_resolve_ms=%.3f "
            "pickup_rz_s=%.3f center_resolve_s=%.3f total_s=%.3f",
            points_elapsed,
            center_elapsed,
            resolver_elapsed,
            registry_elapsed,
            contour_resolve_elapsed,
            len(points_px),
            (contour_resolve_elapsed / max(1, len(points_px))) * 1000.0,
            rz_elapsed,
            center_resolve_elapsed,
            monotonic() - started,
        )
        return {
            "pickup_xy": (float(center_result.final_xy[0]), float(center_result.final_xy[1])),
            "pickup_rz": float(pickup_rz),
            "robot_contour_xy": robot_contour_xy,
        }

    def _resolver(self):
        getter = self._resolver_getter
        if callable(getter):
            try:
                return getter()
            except Exception:
                _logger.exception("[MAGAZINE_LOAD] Failed to get vision resolver")
                return None
        return None

    def _verify_current_capture_pose(
        self,
        group_name: str,
        *,
        position_tolerance_mm: float = 2.0,
        orientation_tolerance_deg: float = 2.0,
    ) -> tuple[bool, str]:
        """Verify the live robot pose against the configured capture group."""
        expected = self._validated_pose(self._navigation.get_group_position(group_name))
        try:
            actual = read_fresh_pose(
                self._path_executor._robot_service,
                error_message="Failed to read fresh robot pose before magazine capture",
            )
        except FreshPoseReadError as exc:
            _logger.error("[MAGAZINE_CAPTURE_POSE] %s", exc)
            actual = None
        if expected is None:
            return False, f"Magazine capture group '{group_name}' has no valid configured pose"
        if actual is None:
            return False, "Fresh robot pose is unavailable before magazine capture"

        xyz_delta = [actual[index] - expected[index] for index in range(3)]
        angle_delta = [
            (actual[index] - expected[index] + 180.0) % 360.0 - 180.0
            for index in range(3, 6)
        ]
        position_error = math.sqrt(sum(delta * delta for delta in xyz_delta))
        orientation_error = max(abs(delta) for delta in angle_delta)
        verified = (
            position_error <= float(position_tolerance_mm)
            and orientation_error <= float(orientation_tolerance_deg)
        )
        _logger.info(
            "[MAGAZINE_CAPTURE_POSE] group=%s verified=%s "
            "configured=(%.3f, %.3f, %.3f, %.3f, %.3f, %.3f) "
            "actual=(%.3f, %.3f, %.3f, %.3f, %.3f, %.3f) "
            "delta_xyz=(%.3f, %.3f, %.3f) delta_rpy=(%.3f, %.3f, %.3f) "
            "position_error_mm=%.3f tolerance_mm=%.3f "
            "orientation_error_deg=%.3f tolerance_deg=%.3f",
            str(group_name),
            verified,
            *expected,
            *actual,
            *xyz_delta,
            *angle_delta,
            position_error,
            float(position_tolerance_mm),
            orientation_error,
            float(orientation_tolerance_deg),
        )
        if not verified:
            return False, (
                f"Magazine capture refused: robot is not at configured group '{group_name}' "
                f"(position error {position_error:.3f} mm, allowed {position_tolerance_mm:.3f} mm; "
                f"orientation error {orientation_error:.3f} deg, allowed "
                f"{orientation_tolerance_deg:.3f} deg)"
            )
        return True, ""

    @staticmethod
    def _validated_pose(pose) -> list[float] | None:
        try:
            values = [float(value) for value in list(pose)[:6]]
        except (TypeError, ValueError):
            return None
        if len(values) != 6 or not all(math.isfinite(value) for value in values):
            return None
        return values

    @staticmethod
    def _wait(seconds: float, stop_requested: Callable[[], bool]) -> bool:
        try:
            duration = max(0.0, float(seconds))
        except (TypeError, ValueError):
            duration = 0.0
        deadline = monotonic() + duration
        while monotonic() < deadline:
            if stop_requested():
                return False
            sleep(min(0.05, max(0.0, deadline - monotonic())))
        return not stop_requested()


def _contour_points_array(contour) -> np.ndarray:
    arr = np.asarray(contour, dtype=np.float64)
    if arr.ndim == 3 and arr.shape[1] == 1:
        arr = arr[:, 0, :]
    try:
        return arr.reshape(-1, 2)
    except ValueError:
        return np.empty((0, 2), dtype=np.float64)


def _contour_center_px(points: np.ndarray) -> tuple[float, float] | None:
    if points.size == 0:
        return None
    contour = points.astype(np.float32).reshape(-1, 1, 2)
    moments = cv2.moments(contour)
    if abs(float(moments.get("m00", 0.0))) > 1e-9:
        return float(moments["m10"] / moments["m00"]), float(moments["m01"] / moments["m00"])
    return float(np.mean(points[:, 0])), float(np.mean(points[:, 1]))

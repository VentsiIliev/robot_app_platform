from __future__ import annotations

import logging
from time import monotonic, sleep
from typing import Callable

import cv2
import numpy as np

from src.engine.robot.path_preparation.geometry import compute_pickup_rz_from_min_rect_long_axis
from src.engine.robot.targeting.vision_pose_request import VisionPoseRequest
from src.robot_systems.paint.processes.paint.config import PaintMagazineLoadConfig
from src.robot_systems.paint.processes.paint.magazine_load_result import NO_WORKPIECE_AT_MAGAZINE
from src.robot_systems.paint.processes.paint.plan import pick_largest_contour

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
        self._target_point_name = str(target_point_name or "tool").strip().lower()
        self._camera_point_name = str(camera_point_name or "camera").strip().lower()
        self._frame_name = str(frame_name or "magazine").strip().lower()
        self._release_work_area_id = str(release_work_area_id or "paint").strip().lower()
        self._release_frame_name = str(release_frame_name or "calibration").strip().lower()

    def load_to_calibration(
        self,
        config: PaintMagazineLoadConfig,
        stop_requested: Callable[[], bool],
    ) -> tuple[bool, str]:
        magazine_group = str(config.magazine_group_id or "Magazine").strip()
        calibration_group = str(config.calibration_group_id or "CALIBRATION").strip()
        if not magazine_group:
            return False, "Magazine movement group is not configured"
        if not calibration_group:
            return False, "Calibration movement group is not configured"

        if not self._navigation.move_to_group(
            magazine_group,
            wait_cancelled=stop_requested,
            velocity=float(config.move_to_magazine_vel_percent),
            acceleration=float(config.move_to_magazine_acc_percent),
        ):
            return False, f"Move to magazine group '{magazine_group}' failed"
        _logger.info("[MAGAZINE_LOAD] Moved to magazine group '%s'", magazine_group)
        if not self._wait(config.camera_settle_s, stop_requested):
            return False, "Paint process stopped"

        snapshot = self._capture_snapshot_service.capture_snapshot(source="paint_magazine_load")
        _logger.info(
            "[MAGAZINE_LOAD] Captured magazine snapshot contours=%d",
            len(snapshot.contours or []),
        )
        if stop_requested():
            return False, "Paint process stopped"

        contour = pick_largest_contour(snapshot.contours)
        if contour is None:
            _logger.warning("[MAGAZINE_LOAD] No usable contour detected after moving to '%s'", magazine_group)
            return False, NO_WORKPIECE_AT_MAGAZINE

        magazine_pose = self._navigation.get_group_position(magazine_group)
        if magazine_pose is None:
            return False, f"Magazine movement group '{magazine_group}' is not configured"
        release_pose = self._navigation.get_group_position(calibration_group)
        if release_pose is None:
            return False, f"Calibration movement group '{calibration_group}' is not configured"
        target = self._resolve_pickup_target(contour, magazine_pose)
        if target is None:
            return False, "Could not resolve magazine pickup target"
        release_pose = self._resolve_work_area_center_release_pose(
            base_pose=release_pose,
            frame=snapshot.frame,
        )
        if release_pose is None:
            return False, f"Could not resolve {self._release_work_area_id} work area center release pose"

        execute_transfer = getattr(self._path_executor, "execute_pickup_target_and_release_at_position", None)
        if not callable(execute_transfer):
            return False, "Paint path executor does not support magazine transfer"
        ok, msg = execute_transfer(
            pickup_xy=target["pickup_xy"],
            pickup_rz=target["pickup_rz"],
            pickup_base_pose=magazine_pose,
            release_pose=release_pose,
            workpiece_height_mm=0.0,
            release_label=f"{self._release_work_area_id} work area center",
        )
        if not ok:
            return False, f"Magazine contour: {msg}"

        if stop_requested():
            return False, "Paint process stopped"
        if not self._navigation.move_to_group(
            calibration_group,
            wait_cancelled=stop_requested,
            velocity=float(config.transfer_to_calibration_vel_percent),
            acceleration=float(config.transfer_to_calibration_acc_percent),
        ):
            return False, f"Move to calibration group '{calibration_group}' after release failed"

        mark_verified = getattr(self._navigation, "mark_group_observed_area_verified", None)
        if callable(mark_verified):
            mark_verified(calibration_group)
        if not self._wait(config.release_settle_s, stop_requested):
            return False, "Paint process stopped"
        return True, f"Magazine contour: {msg}"

    def _resolve_work_area_center_release_pose(self, *, base_pose: list[float], frame) -> list[float] | None:
        if len(base_pose) < 6:
            return None
        center_px = self._release_work_area_center_px(frame)
        if center_px is None:
            return None
        resolver = self._resolver()
        if resolver is None:
            return None
        target_point = resolver.registry.by_name(self._target_point_name)
        result = resolver.resolve(
            VisionPoseRequest(
                x_pixels=float(center_px[0]),
                y_pixels=float(center_px[1]),
                z_mm=float(base_pose[2]),
                rx_degrees=float(base_pose[3]),
                ry_degrees=float(base_pose[4]),
                rz_degrees=float(base_pose[5]),
            ),
            target_point,
            frame=self._release_frame_name,
        )
        release_pose = list(base_pose)
        release_pose[0] = float(result.final_xy[0])
        release_pose[1] = float(result.final_xy[1])
        _logger.info(
            "[MAGAZINE_LOAD] release target work_area=%s frame=%s center_px=(%.3f, %.3f) release_xy=(%.3f, %.3f)",
            self._release_work_area_id,
            self._release_frame_name,
            float(center_px[0]),
            float(center_px[1]),
            float(release_pose[0]),
            float(release_pose[1]),
        )
        return release_pose

    def _release_work_area_center_px(self, frame) -> tuple[float, float] | None:
        if self._work_area_service is None or frame is None or not hasattr(frame, "shape"):
            return None
        try:
            height, width = frame.shape[:2]
        except Exception:
            return None
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
        return _contour_center_px(points_px)

    def _resolve_pickup_target(self, contour, magazine_pose: list[float]) -> dict | None:
        points_px = _contour_points_array(contour)
        if len(points_px) < 3 or len(magazine_pose) < 6:
            return None
        center_px = _contour_center_px(points_px)
        if center_px is None:
            return None
        resolver = self._resolver()
        if resolver is None:
            return None
        camera_point = resolver.registry.by_name(self._camera_point_name)
        target_point = resolver.registry.by_name(self._target_point_name)
        reference_rz = float(magazine_pose[5])
        rx = float(magazine_pose[3])
        ry = float(magazine_pose[4])
        z = float(magazine_pose[2])
        robot_contour_xy = []
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
        pickup_rz = compute_pickup_rz_from_min_rect_long_axis(robot_contour_xy, reference_rz)
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
        _logger.info(
            "[MAGAZINE_LOAD] simple pickup target center_px=(%.3f, %.3f) pickup_xy=(%.3f, %.3f) pickup_rz=%.3f contour_points=%d",
            float(center_px[0]),
            float(center_px[1]),
            float(center_result.final_xy[0]),
            float(center_result.final_xy[1]),
            float(pickup_rz),
            len(points_px),
        )
        return {
            "pickup_xy": (float(center_result.final_xy[0]), float(center_result.final_xy[1])),
            "pickup_rz": float(pickup_rz),
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

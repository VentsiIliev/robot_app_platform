from __future__ import annotations

import logging
import math
import threading
from time import monotonic, sleep
from typing import Callable

import cv2
import numpy as np

from src.engine.robot.path_preparation.geometry import compute_pickup_rz_from_min_rect_long_axis
from src.engine.robot.targeting.vision_pose_request import VisionPoseRequest
from src.robot_systems.paint.processes.paint.config import PaintMagazineLoadConfig
from src.robot_systems.paint.processes.paint.magazine_load.context import MagazineLoadContext
from src.robot_systems.paint.processes.paint.magazine_load.machine_factory import MagazineLoadMachineFactory

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
        self._control_lock = threading.Lock()
        self._active_context: MagazineLoadContext | None = None
        self._machine_factory = MagazineLoadMachineFactory()

    def load_to_calibration(
        self,
        config: PaintMagazineLoadConfig,
        stop_requested: Callable[[], bool],
    ) -> tuple[bool, str]:
        context = MagazineLoadContext(
            service=self,
            config=config,
            stop_requested=stop_requested,
        )
        with self._control_lock:
            self._active_context = context
        try:
            machine = self._machine_factory.build(context)
            machine.start_execution()
            return context.result_ok, context.result_message
        finally:
            with self._control_lock:
                if self._active_context is context:
                    self._active_context = None

    def pause_current_load(self) -> None:
        with self._control_lock:
            context = self._active_context
        if context is None:
            return
        context.run_allowed.clear()
        stop_motion = getattr(self._navigation, "stop_motion", None)
        if callable(stop_motion):
            try:
                stop_motion()
            except Exception:
                _logger.exception("[MAGAZINE_LOAD] Failed to stop robot motion during pause")

    def resume_current_load(self) -> None:
        with self._control_lock:
            context = self._active_context
        if context is not None:
            context.run_allowed.set()

    def stop_current_load(self) -> None:
        with self._control_lock:
            context = self._active_context
        if context is None:
            return
        context.stop_event.set()
        context.run_allowed.set()

    def get_control_snapshot(self) -> dict:
        with self._control_lock:
            context = self._active_context
        return context.snapshot_dict() if context is not None else {}

    def _move_to_group_with_pause_resume_recovery(
        self,
        context: MagazineLoadContext,
        state,
        group_name: str,
        *,
        velocity: float,
        acceleration: float,
        motion_type: str | None = None,
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
            return True
        if context.motion_cancel_requested() or not context.consume_resume_retry():
            return ok

        _logger.warning(
            "[MAGAZINE_LOAD] Move to group '%s' failed immediately after resuming %s; "
            "waiting for controller recovery and retrying once",
            group_name,
            getattr(state, "name", state),
        )
        if not self._wait_after_pause_resume(context):
            return False
        return self._navigation.move_to_group(
            group_name,
            wait_cancelled=context.motion_cancel_requested,
            velocity=velocity,
            acceleration=acceleration,
            motion_type=motion_type,
            blendR=blendR,
        )

    def _wait_after_pause_resume(self, context: MagazineLoadContext) -> bool:
        return self._wait(1.0, context.motion_cancel_requested)

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
        _logger.info(
            "[MAGAZINE_LOAD_TIMING] release_pose center_px_s=%.3f resolver_s=%.3f registry_s=%.3f "
            "resolve_s=%.3f total_s=%.3f",
            center_elapsed,
            resolver_elapsed,
            registry_elapsed,
            resolve_elapsed,
            monotonic() - started,
        )
        return release_pose

    def _release_work_area_center_px(self, frame) -> tuple[float, float] | None:
        started = monotonic()
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
        center = _contour_center_px(points_px)
        _logger.info(
            "[MAGAZINE_LOAD_TIMING] release_work_area_center_px total_s=%.3f points=%d frame_size=%dx%d",
            monotonic() - started,
            len(points_px),
            int(width),
            int(height),
        )
        return center

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
        _logger.info(
            "[MAGAZINE_LOAD] simple pickup target center_px=(%.3f, %.3f) pickup_xy=(%.3f, %.3f) pickup_rz=%.3f contour_points=%d",
            float(center_px[0]),
            float(center_px[1]),
            float(center_result.final_xy[0]),
            float(center_result.final_xy[1]),
            float(pickup_rz),
            len(points_px),
        )
        _logger.info(
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

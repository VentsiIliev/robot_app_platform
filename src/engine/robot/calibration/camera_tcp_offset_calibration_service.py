import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Optional, Protocol

import numpy as np

from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.robot.configuration import RobotCalibrationSettings, RobotSettings
from src.engine.vision.homography_transformer import HomographyTransformer

_logger = logging.getLogger(__name__)


class _IRobotService(Protocol):
    def get_current_position(self) -> list: ...

    def move_ptp(
        self,
        position,
        tool,
        user,
        velocity,
        acceleration,
        wait_to_reach=False,
    ) -> bool: ...

    def stop_motion(self) -> bool: ...


class _IVisionService(Protocol):
    def get_latest_frame(self): ...

    def detect_aruco_markers(self, image): ...

    def get_camera_width(self) -> int: ...

    def get_camera_height(self) -> int: ...

    @property
    def camera_to_robot_matrix_path(self) -> str: ...


class _INavigationService(Protocol):
    def move_to_calibration_position(self, wait_cancelled=None) -> bool: ...


@dataclass(frozen=True)
class _MarkerSample:
    sample_index: int
    rz: float
    measured_world_dx: float
    measured_world_dy: float
    local_dx: float
    local_dy: float
    pixel_error_x: float
    pixel_error_y: float
    pixel_error_norm: float


class CameraTcpOffsetCalibrationService:
    """Calibrate camera-center to robot-TCP XY offsets using one ArUco marker."""

    def __init__(
        self,
        *,
        vision_service: _IVisionService,
        robot_service: _IRobotService,
        navigation_service: Optional[_INavigationService],
        settings_service: ISettingsService,
        robot_config_key,
        robot_config: RobotSettings,
        calibration_settings: RobotCalibrationSettings,
        robot_tool: int,
        robot_user: int,
    ):
        self._vision = vision_service
        self._robot = robot_service
        self._navigation = navigation_service
        self._settings = settings_service
        self._robot_config_key = robot_config_key
        self._robot_config = robot_config
        self._calibration_settings = calibration_settings
        self._tool = robot_tool
        self._user = robot_user
        self._stop_event = threading.Event()
        self._transformer = HomographyTransformer(vision_service.camera_to_robot_matrix_path)

    def stop(self) -> None:
        self._stop_event.set()
        try:
            self._robot.stop_motion()
        except Exception:
            pass

    def calibrate(self) -> tuple[bool, str]:
        cfg = self._calibration_settings.camera_tcp_offset
        self._stop_event.clear()
        self._transformer.reload()
        if not self._transformer.is_available():
            return False, "Homography matrix not available"
        draw_contours_was_enabled = self._get_draw_contours_state()
        if draw_contours_was_enabled:
            _logger.info("Disabling contour drawing for camera TCP offset calibration")
            self._vision.set_draw_contours(False)

        try:
            _logger.info(
                "Starting camera TCP offset calibration: marker_id=%d iterations=%d rotation_step_deg=%.3f "
                "approach=(z=%.3f rx_degrees=%.3f ry_degrees=%.3f rz_degrees=%.3f) motion=(vel=%d acc=%d)",
                cfg.marker_id,
                cfg.iterations,
                cfg.rotation_step_deg,
                cfg.approach_z,
                cfg.approach_rx,
                cfg.approach_ry,
                cfg.approach_rz,
                cfg.velocity,
                cfg.acceleration,
            )

            if self._navigation is not None:
                _logger.info("Moving to calibration position before sampling")
                ok = self._navigation.move_to_calibration_position(wait_cancelled=self._stop_event.is_set)
                if not ok:
                    return False, "Failed to move to calibration position"

            initial_detection = self._detect_marker_center(cfg.marker_id, "initial target acquisition")
            if initial_detection is None:
                return False, f"Marker {cfg.marker_id} not detected for initial target acquisition"

            target_px, target_py = initial_detection
            target_x, target_y = self._transformer.transform(target_px, target_py)
            _logger.info(
                "Initial marker detection: x_pixels=(%.3f, %.3f) -> camera-center robot target=(%.3f, %.3f)",
                target_px,
                target_py,
                target_x,
                target_y,
            )

            initial_pose = [
                target_x,
                target_y,
                cfg.approach_z,
                cfg.approach_rx,
                cfg.approach_ry,
                cfg.approach_rz,
            ]
            if not self._move(initial_pose, cfg.velocity, cfg.acceleration, "initial center approach"):
                return False, "Failed to move to initial marker-centered pose"

            samples: list[_MarkerSample] = []
            for index in range(1, cfg.iterations + 1):
                if self._stop_event.is_set():
                    return False, "Camera TCP offset calibration stopped"

                sample_rz = cfg.approach_rz + index * cfg.rotation_step_deg
                sample_pose = [
                    target_x,
                    target_y,
                    cfg.approach_z,
                    cfg.approach_rx,
                    cfg.approach_ry,
                    sample_rz,
                ]
                if not self._move(sample_pose, cfg.velocity, cfg.acceleration, f"sample {index + 1}/{cfg.iterations}"):
                    return False, f"Failed to move for sample {index + 1}"

                if self._interruptible_sleep(cfg.settle_time_s):
                    return False, "Camera TCP offset calibration stopped"

                sample = self._measure_sample(
                    index=index - 1,
                    sample_rz=sample_rz,
                    reference_rz=cfg.approach_rz,
                )
                if sample is None:
                    return False, f"Marker {cfg.marker_id} not detected for sample {index}"
                samples.append(sample)

            if not samples:
                return False, "No valid samples collected"

            offset_x = float(np.mean([s.local_dx for s in samples]))
            offset_y = float(np.mean([s.local_dy for s in samples]))
            std_x = float(np.std([s.local_dx for s in samples]))
            std_y = float(np.std([s.local_dy for s in samples]))

            _logger.info(
                "Solved camera-to-TCP offset from %d samples: camera_to_tcp_x_offset=%.6f camera_to_tcp_y_offset=%.6f std=(%.6f, %.6f)",
                len(samples),
                offset_x,
                offset_y,
                std_x,
                std_y,
            )

            self._robot_config.camera_to_tcp_x_offset = offset_x
            self._robot_config.camera_to_tcp_y_offset = offset_y
            self._settings.save(self._robot_config_key, self._robot_config)
            _logger.info(
                "Saved camera-to-TCP offsets to robot config: camera_to_tcp_x_offset=%.6f camera_to_tcp_y_offset=%.6f",
                offset_x,
                offset_y,
            )

            return True, (
                f"Camera-to-TCP offset calibrated: X={offset_x:.3f} mm, Y={offset_y:.3f} mm "
                f"(std X={std_x:.3f}, Y={std_y:.3f})"
            )
        finally:
            if draw_contours_was_enabled:
                _logger.info("Restoring contour drawing after camera TCP offset calibration")
                self._vision.set_draw_contours(True)

    def _measure_sample(self, *, index: int, sample_rz: float, reference_rz: float) -> Optional[_MarkerSample]:
        cfg = self._calibration_settings.camera_tcp_offset
        detection = self._detect_marker_center(cfg.marker_id, f"sample {index + 1}")
        if detection is None:
            return None
        marker_px, marker_py = detection
        desired_x, desired_y = self._transformer.transform(marker_px, marker_py)
        current_pose = self._robot.get_current_position()
        if not current_pose or len(current_pose) < 6:
            raise RuntimeError("Failed to read current robot position during camera TCP calibration")

        world_dx = float(desired_x - current_pose[0])
        world_dy = float(desired_y - current_pose[1])
        local_dx, local_dy = self._solve_local_offset(
            world_dx,
            world_dy,
            reference_rz_deg=reference_rz,
            sample_rz_deg=sample_rz,
        )

        image_cx = self._vision.get_camera_width() / 2.0
        image_cy = self._vision.get_camera_height() / 2.0
        pixel_error_x = float(marker_px - image_cx)
        pixel_error_y = float(marker_py - image_cy)
        pixel_error_norm = math.hypot(pixel_error_x, pixel_error_y)

        _logger.info(
            "Sample %d: rz_degrees=%.3f marker_px=(%.3f, %.3f) pixel_error=(%.3f, %.3f | norm=%.3f) "
            "desired_camera_center=(%.3f, %.3f) current_pose_xy=(%.3f, %.3f) "
            "world_correction=(%.6f, %.6f) local_estimate=(%.6f, %.6f)",
            index + 1,
            sample_rz,
            marker_px,
            marker_py,
            pixel_error_x,
            pixel_error_y,
            pixel_error_norm,
            desired_x,
            desired_y,
            current_pose[0],
            current_pose[1],
            world_dx,
            world_dy,
            local_dx,
            local_dy,
        )

        return _MarkerSample(
            sample_index=index,
            rz=sample_rz,
            measured_world_dx=world_dx,
            measured_world_dy=world_dy,
            local_dx=local_dx,
            local_dy=local_dy,
            pixel_error_x=pixel_error_x,
            pixel_error_y=pixel_error_y,
            pixel_error_norm=pixel_error_norm,
        )

    def _detect_marker_center(self, marker_id: int, label: str) -> Optional[tuple[float, float]]:
        cfg = self._calibration_settings.camera_tcp_offset
        for attempt in range(1, cfg.detection_attempts + 1):
            if self._stop_event.is_set():
                return None
            frame = self._vision.get_latest_frame()
            if frame is None:
                _logger.debug("%s: no frame available on attempt %d/%d", label, attempt, cfg.detection_attempts)
                self._interruptible_sleep(cfg.retry_delay_s)
                continue
            corners, ids, _ = self._vision.detect_aruco_markers(frame)
            if ids is None:
                _logger.debug("%s: no ArUco markers detected on attempt %d/%d", label, attempt, cfg.detection_attempts)
                self._interruptible_sleep(cfg.retry_delay_s)
                continue
            for detected_id, marker_corners in zip(ids.flatten(), corners):
                if int(detected_id) != marker_id:
                    continue
                center = marker_corners[0].mean(axis=0)
                center_x = float(center[0])
                center_y = float(center[1])
                _logger.debug(
                    "%s: detected marker %d at center x_pixels=(%.3f, %.3f) on attempt %d/%d",
                    label,
                    marker_id,
                    center_x,
                    center_y,
                    attempt,
                    cfg.detection_attempts,
                )
                return center_x, center_y
            _logger.debug(
                "%s: marker %d missing on attempt %d/%d; seen_ids=%s",
                label,
                marker_id,
                attempt,
                cfg.detection_attempts,
                [int(i) for i in ids.flatten()],
            )
            self._interruptible_sleep(cfg.retry_delay_s)
        return None

    def _move(self, pose: list[float], velocity: int, acceleration: int, label: str) -> bool:
        _logger.info(
            "Camera TCP calibration move [%s]: pose=%s tool=%d user=%d vel=%d acc=%d",
            label,
            pose,
            self._tool,
            self._user,
            velocity,
            acceleration,
        )
        ok = self._robot.move_ptp(
            position=pose,
            tool=self._tool,
            user=self._user,
            velocity=velocity,
            acceleration=acceleration,
            wait_to_reach=True,
        )
        _logger.info("Camera TCP calibration move [%s] result=%s", label, ok)
        return bool(ok)

    def _interruptible_sleep(self, seconds: float) -> bool:
        return self._stop_event.wait(timeout=max(0.0, seconds))

    def _get_draw_contours_state(self) -> bool:
        try:
            vision_system = getattr(self._vision, "_vision_system", None)
            camera_settings = getattr(vision_system, "camera_settings", None)
            if camera_settings is None:
                return False
            getter = getattr(camera_settings, "get_draw_contours", None)
            if getter is None:
                return False
            return bool(getter())
        except Exception as exc:
            _logger.debug("Could not read draw_contours state before calibration: %s", exc)
            return False

    @staticmethod
    def _solve_local_offset(
        world_dx: float,
        world_dy: float,
        *,
        reference_rz_deg: float,
        sample_rz_deg: float,
    ) -> tuple[float, float]:
        ref_rad = math.radians(reference_rz_deg)
        sample_rad = math.radians(sample_rz_deg)
        cos_ref = math.cos(ref_rad)
        sin_ref = math.sin(ref_rad)
        cos_sample = math.cos(sample_rad)
        sin_sample = math.sin(sample_rad)

        a = cos_ref - cos_sample
        b = -sin_ref + sin_sample
        c = sin_ref - sin_sample
        d = cos_ref - cos_sample
        det = a * d - b * c
        if math.isclose(det, 0.0, abs_tol=1e-9):
            raise ValueError(
                "TCP offset sample rotation is too small to solve a camera-to-TCP offset"
            )

        local_dx = (d * world_dx - b * world_dy) / det
        local_dy = (-c * world_dx + a * world_dy) / det
        return float(local_dx), float(local_dy)

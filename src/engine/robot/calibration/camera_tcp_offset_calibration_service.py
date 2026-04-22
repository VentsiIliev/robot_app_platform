import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Optional, Protocol

import numpy as np

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.robot.configuration import RobotCalibrationSettings, RobotSettings
from src.engine.robot.configuration.robot_calibration_settings import AxisMappingConfig
from src.engine.robot.enums.axis import AxisMapping, Direction, ImageAxis, ImageToRobotMapping
from src.engine.vision.homography_residual_transformer import HomographyResidualTransformer

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
    marker_px: float
    marker_py: float
    current_pose_x: float
    current_pose_y: float
    measured_world_dx: float
    measured_world_dy: float
    local_dx: float
    local_dy: float
    pixel_error_x: float
    pixel_error_y: float
    pixel_error_norm: float


def _build_tcp_offset_summary(
    samples: list[_MarkerSample],
    *,
    offset_x: float,
    offset_y: float,
    std_x: float,
    std_y: float,
    marker_id: int,
    approach_pose: list[float],
    local_scale_x: float,
    local_scale_y: float,
    reference_rz: float,
    rotation_step_deg: float,
    iterations: int,
) -> str:
    lines = [
        "=== CAMERA TCP OFFSET CALIBRATION SUMMARY ===",
        f"Marker ID: {marker_id}",
        f"Samples used: {len(samples)} / configured_iterations={iterations}",
        "Approach pose: "
        f"[{approach_pose[0]:.3f}, {approach_pose[1]:.3f}, {approach_pose[2]:.3f}, {approach_pose[3]:.3f}, {approach_pose[4]:.3f}, {approach_pose[5]:.3f}]",
        f"Reference RZ: {reference_rz:.3f} deg",
        f"Rotation step: {rotation_step_deg:.3f} deg",
        f"Local scale at image center: ({local_scale_x:.6f}, {local_scale_y:.6f}) mm/px",
        "Raw samples:",
    ]

    if samples:
        weights = np.array([1.0 / max(s.pixel_error_norm, 1.0) for s in samples], dtype=np.float64)
        weights = weights / weights.sum()
        dx_arr = np.array([s.local_dx for s in samples], dtype=np.float64)
        dy_arr = np.array([s.local_dy for s in samples], dtype=np.float64)
        px_arr = np.array([s.pixel_error_norm for s in samples], dtype=np.float64)
    else:
        weights = np.array([], dtype=np.float64)
        dx_arr = np.array([], dtype=np.float64)
        dy_arr = np.array([], dtype=np.float64)
        px_arr = np.array([], dtype=np.float64)

    for idx, sample in enumerate(samples):
        lines.append(
            "  "
            f"idx={sample.sample_index} rz={sample.rz:.3f} "
            f"marker_px=({sample.marker_px:.3f}, {sample.marker_py:.3f}) "
            f"robot_xy=({sample.current_pose_x:.3f}, {sample.current_pose_y:.3f}) "
            f"pixel_error=({sample.pixel_error_x:.3f}, {sample.pixel_error_y:.3f} | norm={sample.pixel_error_norm:.3f}) "
            f"world=({sample.measured_world_dx:.6f}, {sample.measured_world_dy:.6f}) "
            f"local=({sample.local_dx:.6f}, {sample.local_dy:.6f}) "
            f"weight={weights[idx]:.4f}"
        )

    if samples:
        lines.extend(
            [
                "Aggregate:",
                f"  solved_local=({offset_x:.6f}, {offset_y:.6f})",
                f"  residual_std=({std_x:.6f}, {std_y:.6f})",
                f"  local_x_range=({dx_arr.min():.6f}, {dx_arr.max():.6f}) span={dx_arr.max() - dx_arr.min():.6f}",
                f"  local_y_range=({dy_arr.min():.6f}, {dy_arr.max():.6f}) span={dy_arr.max() - dy_arr.min():.6f}",
                f"  pixel_error_norm_range=({px_arr.min():.3f}, {px_arr.max():.3f})",
            ]
        )
    lines.append("============================================")
    return "\n".join(lines)


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
        self._transformer = HomographyResidualTransformer(vision_service.camera_to_robot_matrix_path)
        self._image_to_robot_mapping: Optional[ImageToRobotMapping] = None

    def stop(self) -> None:
        self._stop_event.set()
        try:
            self._robot.stop_motion()
        except Exception:
            pass

    def calibrate(self) -> tuple[bool, str]:
        self._refresh_runtime_settings()
        cfg = self._calibration_settings.camera_tcp_offset
        self._stop_event.clear()
        self._transformer.reload()
        if not self._transformer.is_available():
            return False, "Homography matrix not available"
        effective_iterations = max(1, int(cfg.iterations))
        draw_contours_was_enabled = self._get_draw_contours_state()
        if draw_contours_was_enabled:
            _logger.info("Disabling contour drawing for camera TCP offset calibration")
            self._vision.set_draw_contours(False)
        auto_brightness_locked = False
        auto_brightness_adjustment_locked = False

        try:
            _logger.info(
                "Starting camera TCP offset calibration: marker_id=%d iterations=%d rotation_step_deg=%.3f "
                "approach=(z=%.3f rx_degrees=%.3f ry_degrees=%.3f rz_degrees=%.3f) motion=(vel=%d acc=%d)",
                cfg.marker_id,
                effective_iterations,
                cfg.rotation_step_deg,
                cfg.approach_z,
                cfg.approach_rx,
                cfg.approach_ry,
                cfg.approach_rz,
                cfg.velocity,
                cfg.acceleration,
            )
            if hasattr(self._vision, "get_auto_brightness_enabled") and self._vision.get_auto_brightness_enabled():
                if hasattr(self._vision, "lock_auto_brightness_region"):
                    auto_brightness_locked = bool(self._vision.lock_auto_brightness_region())
                    if auto_brightness_locked:
                        _logger.info("Locking auto brightness region during standalone TCP calibration")
                    else:
                        _logger.warning("Unable to lock auto brightness region during standalone TCP calibration")
                if hasattr(self._vision, "lock_auto_brightness_adjustment"):
                    self._vision.lock_auto_brightness_adjustment()
                    auto_brightness_adjustment_locked = True
                    _logger.info("Freezing auto brightness adjustment during standalone TCP calibration")

            if self._navigation is not None:
                _logger.info("Moving to calibration position before sampling")
                ok = self._navigation.move_to_calibration_position(wait_cancelled=self._stop_event.is_set)
                if not ok:
                    return False, "Failed to move to calibration position"

            self._image_to_robot_mapping = self._calibrate_axis_mapping()
            if self._image_to_robot_mapping is None:
                return False, "Failed to calibrate image-to-robot axis mapping for standalone TCP calibration"

            # Compute transformer Jacobian at image centre once.
            # Used as a local linear scale (mm/px) for all sample measurements so that
            # world_dx/dy are derived from pixel offsets rather than evaluating the full
            # transformer at off-centre positions (where its residual error is larger).
            image_cx = self._vision.get_camera_width() / 2.0
            image_cy = self._vision.get_camera_height() / 2.0
            _x0, _y0 = self._transformer.transform(image_cx, image_cy)
            _x1, _   = self._transformer.transform(image_cx + 1.0, image_cy)
            _,   _y1 = self._transformer.transform(image_cx, image_cy + 1.0)
            local_scale_x = _x1 - _x0   # mm per pixel, X direction
            local_scale_y = _y1 - _y0   # mm per pixel, Y direction
            _logger.info(
                "Transformer local scale at image centre: scale_x=%.4f mm/px  scale_y=%.4f mm/px",
                local_scale_x, local_scale_y,
            )

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
            reference_pose = self._recenter_marker_to_center(
                marker_id=cfg.marker_id,
                camera_rotation_deg=0.0,
                local_scale_x=local_scale_x,
                local_scale_y=local_scale_y,
                label="initial recenter",
            )
            if reference_pose is None:
                return False, f"Failed to recenter marker {cfg.marker_id} at initial pose"

            samples: list[_MarkerSample] = []
            try:
                for index in range(1, effective_iterations + 1):
                    if self._stop_event.is_set():
                        return False, "Camera TCP offset calibration stopped"

                    sample_rz = cfg.approach_rz + index * cfg.rotation_step_deg
                    sample_pose = [
                        float(reference_pose[0]),
                        float(reference_pose[1]),
                        float(reference_pose[2]),
                        float(reference_pose[3]),
                        float(reference_pose[4]),
                        float(sample_rz),
                    ]
                    _logger.info(
                        "Camera TCP sample %d/%d: rotate from reference_rz=%.3f to sample_rz=%.3f",
                        index,
                        effective_iterations,
                        cfg.approach_rz,
                        sample_rz,
                    )
                    if not self._move(sample_pose, cfg.velocity, cfg.acceleration, f"sample {index}/{effective_iterations} rotate"):
                        return False, f"Failed to rotate for sample {index}"

                    if self._interruptible_sleep(cfg.settle_time_s):
                        return False, "Camera TCP offset calibration stopped"
                    aligned_pose = self._recenter_marker_to_center(
                        marker_id=cfg.marker_id,
                        camera_rotation_deg=(sample_rz - cfg.approach_rz),
                        local_scale_x=local_scale_x,
                        local_scale_y=local_scale_y,
                        label=f"sample {index} recenter",
                    )
                    if aligned_pose is None:
                        return False, f"Failed to recenter marker {cfg.marker_id} for sample {index}"

                    sample = self._measure_sample(
                        index=index - 1,
                        sample_rz=sample_rz,
                        reference_rz=cfg.approach_rz,
                        reference_pose=reference_pose,
                        aligned_pose=aligned_pose,
                    )
                    if sample is None:
                        return False, f"Marker {cfg.marker_id} not detected for sample {index}"
                    samples.append(sample)

                    if not self._move(reference_pose, cfg.velocity, cfg.acceleration, f"restore reference after sample {index}"):
                        return False, f"Failed to restore reference pose after sample {index}"
                    if self._interruptible_sleep(cfg.recenter_stability_wait_s):
                        return False, "Camera TCP offset calibration stopped"
            finally:
                self._move(reference_pose, cfg.velocity, cfg.acceleration, "final reference restore")

            if not samples:
                return False, "No valid samples collected"

            # Global weighted least-squares across all samples.
            # Each sample contributes two rows to the linear system:
            #   (cos_ref - cos_i)*ldx + (sin_i - sin_ref)*ldy = world_dx_i
            #   (sin_ref - sin_i)*ldx + (cos_ref - cos_i)*ldy = world_dy_i
            # Solving jointly avoids the small-determinant amplification that occurs
            # when solving each sample independently (especially for small rotation angles).
            ref_rad = math.radians(cfg.approach_rz)
            cos_ref = math.cos(ref_rad)
            sin_ref = math.sin(ref_rad)
            A_rows, b_rows, w_rows = [], [], []
            for s in samples:
                s_rad = math.radians(s.rz)
                cos_s, sin_s = math.cos(s_rad), math.sin(s_rad)
                w = 1.0 / max(s.pixel_error_norm, 1.0)
                A_rows += [[cos_ref - cos_s, sin_s - sin_ref],
                            [sin_ref - sin_s, cos_ref - cos_s]]
                b_rows += [s.measured_world_dx, s.measured_world_dy]
                w_rows += [w, w]
            A = np.array(A_rows, dtype=np.float64)
            b = np.array(b_rows, dtype=np.float64)
            W = np.array(w_rows, dtype=np.float64)
            result, _, _, _ = np.linalg.lstsq(A * W[:, None], b * W, rcond=None)
            offset_x, offset_y = float(result[0]), float(result[1])

            # Residual std as quality indicator
            residuals = b - A @ result
            std_x = float(np.std(residuals[0::2]))
            std_y = float(np.std(residuals[1::2]))

            _logger.info(
                _build_tcp_offset_summary(
                    samples,
                    offset_x=offset_x,
                    offset_y=offset_y,
                    std_x=std_x,
                    std_y=std_y,
                    marker_id=cfg.marker_id,
                    approach_pose=initial_pose,
                    local_scale_x=local_scale_x,
                    local_scale_y=local_scale_y,
                    reference_rz=cfg.approach_rz,
                    rotation_step_deg=cfg.rotation_step_deg,
                    iterations=effective_iterations,
                )
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
            if auto_brightness_adjustment_locked and hasattr(self._vision, "unlock_auto_brightness_adjustment"):
                _logger.info("Restoring adaptive auto brightness adjustment after standalone TCP calibration")
                self._vision.unlock_auto_brightness_adjustment()
            if auto_brightness_locked and hasattr(self._vision, "unlock_auto_brightness_region"):
                _logger.info("Restoring dynamic auto brightness region after standalone TCP calibration")
                self._vision.unlock_auto_brightness_region()

    def _refresh_runtime_settings(self) -> None:
        try:
            latest_calibration_settings = self._settings.get(CommonSettingsID.ROBOT_CALIBRATION)
            if latest_calibration_settings is not None:
                self._calibration_settings = latest_calibration_settings
        except Exception as exc:
            _logger.warning("Could not refresh robot calibration settings before standalone TCP calibration: %s", exc)

        try:
            latest_robot_settings = self._settings.get(self._robot_config_key)
            if latest_robot_settings is not None:
                self._robot_config = latest_robot_settings
        except Exception as exc:
            _logger.warning("Could not refresh robot settings before standalone TCP calibration: %s", exc)

    def _measure_sample(
        self,
        *,
        index: int,
        sample_rz: float,
        reference_rz: float,
        reference_pose: list[float],
        aligned_pose: list[float],
    ) -> Optional[_MarkerSample]:
        cfg = self._calibration_settings.camera_tcp_offset
        detection = self._detect_marker_center(cfg.marker_id, f"sample {index + 1}")
        if detection is None:
            return None
        marker_px, marker_py = detection

        world_dx = float(aligned_pose[0] - reference_pose[0])
        world_dy = float(aligned_pose[1] - reference_pose[1])
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
            "current_pose_xy=(%.3f, %.3f) world_correction=(%.6f, %.6f) local_estimate=(%.6f, %.6f)",
            index + 1,
            sample_rz,
            marker_px,
            marker_py,
            pixel_error_x,
            pixel_error_y,
            pixel_error_norm,
            aligned_pose[0],
            aligned_pose[1],
            world_dx,
            world_dy,
            local_dx,
            local_dy,
        )

        return _MarkerSample(
            sample_index=index,
            rz=sample_rz,
            marker_px=marker_px,
            marker_py=marker_py,
            current_pose_x=float(aligned_pose[0]),
            current_pose_y=float(aligned_pose[1]),
            measured_world_dx=world_dx,
            measured_world_dy=world_dy,
            local_dx=local_dx,
            local_dy=local_dy,
            pixel_error_x=pixel_error_x,
            pixel_error_y=pixel_error_y,
            pixel_error_norm=pixel_error_norm,
        )

    def _detect_marker_center(self, marker_id: int, label: str, n_avg: int = 3) -> Optional[tuple[float, float]]:
        """Detect marker center averaged over n_avg successful detections to reduce frame noise."""
        cfg = self._calibration_settings.camera_tcp_offset
        detections: list[tuple[float, float]] = []
        attempts = 0
        max_attempts = cfg.detection_attempts * n_avg
        while len(detections) < n_avg and attempts < max_attempts:
            attempts += 1
            if self._stop_event.is_set():
                return None
            frame = self._vision.get_latest_frame()
            if frame is None:
                _logger.debug("%s: no frame available (attempt %d)", label, attempts)
                self._interruptible_sleep(cfg.retry_delay_s)
                continue
            corners, ids, _ = self._vision.detect_aruco_markers(frame)
            if ids is None:
                _logger.debug("%s: no ArUco markers detected (attempt %d)", label, attempts)
                self._interruptible_sleep(cfg.retry_delay_s)
                continue
            ids_flat = np.asarray(ids).flatten()
            found = False
            for detected_id, marker_corners in zip(ids_flat, corners):
                if int(detected_id) != marker_id:
                    continue
                center = marker_corners[0].mean(axis=0)
                detections.append((float(center[0]), float(center[1])))
                found = True
                break
            if not found:
                _logger.debug(
                    "%s: marker %d missing (attempt %d); seen_ids=%s",
                    label, marker_id, attempts, [int(i) for i in ids_flat],
                )
                self._interruptible_sleep(cfg.retry_delay_s)

        if not detections:
            return None

        center_x = float(np.mean([d[0] for d in detections]))
        center_y = float(np.mean([d[1] for d in detections]))
        _logger.debug(
            "%s: marker %d averaged over %d frames -> center x_pixels=(%.3f, %.3f)",
            label, marker_id, len(detections), center_x, center_y,
        )
        return center_x, center_y

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

    def _recenter_marker_to_center(
        self,
        *,
        marker_id: int,
        camera_rotation_deg: float,
        local_scale_x: float,
        local_scale_y: float,
        label: str,
    ) -> Optional[list[float]]:
        cfg = self._calibration_settings.camera_tcp_offset
        image_cx = self._vision.get_camera_width() / 2.0
        image_cy = self._vision.get_camera_height() / 2.0

        for iteration in range(1, int(cfg.recenter_max_iterations) + 1):
            detection = self._detect_marker_center(marker_id, f"{label} iter {iteration}", n_avg=1)
            if detection is None:
                _logger.warning("%s: marker %d not found during recenter iteration %d", label, marker_id, iteration)
                continue

            marker_px, marker_py = detection
            pixel_error_x = float(marker_px - image_cx)
            pixel_error_y = float(marker_py - image_cy)
            pixel_error_norm = math.hypot(pixel_error_x, pixel_error_y)
            scale_x_mm_per_px = abs(float(local_scale_x))
            scale_y_mm_per_px = abs(float(local_scale_y))
            offset_x_mm = float(pixel_error_x * scale_x_mm_per_px)
            offset_y_mm = float(pixel_error_y * scale_y_mm_per_px)
            error_mm = math.hypot(offset_x_mm, offset_y_mm)
            recenter_alignment_threshold_mm = max(
                1e-6,
                float(getattr(cfg, "recenter_alignment_threshold_mm", 0.5)),
            )
            if error_mm <= recenter_alignment_threshold_mm:
                current_pose = self._robot.get_current_position()
                _logger.info(
                    "%s: converged iter=%d marker_px=(%.3f, %.3f) pixel_error=(%.3f, %.3f | norm=%.3f px ~= %.3f mm)",
                    label,
                    iteration,
                    marker_px,
                    marker_py,
                    pixel_error_x,
                    pixel_error_y,
                    pixel_error_norm,
                    error_mm,
                )
                return list(current_pose) if current_pose else None

            if abs(float(camera_rotation_deg)) > 1e-9:
                theta = math.radians(float(camera_rotation_deg))
                cos_t = math.cos(theta)
                sin_t = math.sin(theta)
                derotated_x_mm = offset_x_mm * cos_t + offset_y_mm * sin_t
                derotated_y_mm = -offset_x_mm * sin_t + offset_y_mm * cos_t
            else:
                derotated_x_mm = offset_x_mm
                derotated_y_mm = offset_y_mm

            if self._image_to_robot_mapping is None:
                raise RuntimeError("Standalone TCP recenter called without image-to-robot mapping")
            mapped_x_mm, mapped_y_mm = self._image_to_robot_mapping.map(derotated_x_mm, derotated_y_mm)
            move_x_mm, move_y_mm = self._compute_iterative_move(
                current_error_mm=error_mm,
                correction_x_mm=mapped_x_mm,
                correction_y_mm=mapped_y_mm,
            )
            current_pose = self._robot.get_current_position()
            if not current_pose or len(current_pose) < 6:
                raise RuntimeError("Failed to read current robot position during standalone TCP recenter")
            target_pose = [
                float(current_pose[0]) + move_x_mm,
                float(current_pose[1]) + move_y_mm,
                float(current_pose[2]),
                float(current_pose[3]),
                float(current_pose[4]),
                float(current_pose[5]),
            ]
            _logger.info(
                "%s: iter=%d marker_px=(%.3f, %.3f) pixel_error=(%.3f, %.3f | norm=%.3f px ~= %.3f mm) "
                "offset_mm=(%.3f, %.3f) derotated_mm=(%.3f, %.3f) mapped_mm=(%.3f, %.3f) "
                "move_mm=(%.3f, %.3f) -> target_xy=(%.3f, %.3f)",
                label,
                iteration,
                marker_px,
                marker_py,
                pixel_error_x,
                pixel_error_y,
                pixel_error_norm,
                error_mm,
                offset_x_mm,
                offset_y_mm,
                derotated_x_mm,
                derotated_y_mm,
                mapped_x_mm,
                mapped_y_mm,
                move_x_mm,
                move_y_mm,
                target_pose[0],
                target_pose[1],
            )
            if not self._move(target_pose, cfg.velocity, cfg.acceleration, f"{label} iter {iteration}"):
                return None
            if self._interruptible_sleep(cfg.recenter_stability_wait_s):
                return None

        _logger.warning(
            "%s: failed to recenter marker %d after %d iterations",
            label,
            marker_id,
            int(cfg.recenter_max_iterations),
        )
        return None

    def _interruptible_sleep(self, seconds: float) -> bool:
        return self._stop_event.wait(timeout=max(0.0, seconds))

    def _calibrate_axis_mapping(self) -> Optional[ImageToRobotMapping]:
        cfg = self._calibration_settings.axis_mapping or AxisMappingConfig()
        marker_id = int(cfg.marker_id)
        move_mm = float(cfg.move_mm)
        delay_s = float(cfg.delay_after_move_s)

        before_x = self._detect_marker_center(marker_id, "axis mapping +X before", n_avg=1)
        if before_x is None:
            _logger.warning("Standalone TCP axis mapping: marker %d not found before +X move", marker_id)
            return None

        if not self._move_relative(dx_mm=move_mm, dy_mm=0.0, velocity=self._calibration_settings.travel_velocity,
                                   acceleration=self._calibration_settings.travel_acceleration, label="axis mapping +X"):
            return None
        if self._interruptible_sleep(delay_s):
            return None
        after_x = self._detect_marker_center(marker_id, "axis mapping +X after", n_avg=1)
        if after_x is None:
            return None

        if not self._move_relative(dx_mm=-move_mm, dy_mm=0.0, velocity=self._calibration_settings.travel_velocity,
                                   acceleration=self._calibration_settings.travel_acceleration, label="axis mapping restore X"):
            return None

        before_y = self._detect_marker_center(marker_id, "axis mapping -Y before", n_avg=1)
        if before_y is None:
            return None
        if not self._move_relative(dx_mm=0.0, dy_mm=-move_mm, velocity=self._calibration_settings.travel_velocity,
                                   acceleration=self._calibration_settings.travel_acceleration, label="axis mapping -Y"):
            return None
        if self._interruptible_sleep(delay_s):
            return None
        after_y = self._detect_marker_center(marker_id, "axis mapping -Y after", n_avg=1)
        if after_y is None:
            return None

        if not self._move_relative(dx_mm=0.0, dy_mm=move_mm, velocity=self._calibration_settings.travel_velocity,
                                   acceleration=self._calibration_settings.travel_acceleration, label="axis mapping restore Y"):
            return None

        dx_img_xmove = float(after_x[0] - before_x[0])
        dy_img_xmove = float(after_x[1] - before_x[1])
        dx_img_ymove = float(after_y[0] - before_y[0])
        dy_img_ymove = float(after_y[1] - before_y[1])

        def compute_axis_mapping(dx: float, dy: float, robot_move_mm_value: float) -> tuple[ImageAxis, Direction]:
            if abs(dx) > abs(dy):
                image_axis = ImageAxis.X
                img_delta = dx
            else:
                image_axis = ImageAxis.Y
                img_delta = dy
            direction = Direction.PLUS if robot_move_mm_value * img_delta < 0 else Direction.MINUS
            return image_axis, direction

        robot_x_image_axis, robot_x_direction = compute_axis_mapping(dx_img_xmove, dy_img_xmove, move_mm)
        robot_y_image_axis, robot_y_direction = compute_axis_mapping(dx_img_ymove, dy_img_ymove, -move_mm)
        mapping = ImageToRobotMapping(
            robot_x=AxisMapping(image_axis=robot_x_image_axis, direction=robot_x_direction),
            robot_y=AxisMapping(image_axis=robot_y_image_axis, direction=robot_y_direction),
        )
        _logger.info(
            "Standalone TCP axis mapping calibrated: marker=%d move_mm=%.3f "
            "x_move_img_delta=(%.3f, %.3f) -> robot_x=(%s,%s) "
            "y_move_img_delta=(%.3f, %.3f) -> robot_y=(%s,%s)",
            marker_id,
            move_mm,
            dx_img_xmove,
            dy_img_xmove,
            robot_x_image_axis.name,
            robot_x_direction.name,
            dx_img_ymove,
            dy_img_ymove,
            robot_y_image_axis.name,
            robot_y_direction.name,
        )
        return mapping

    def _move_relative(self, *, dx_mm: float, dy_mm: float, velocity: int, acceleration: int, label: str) -> bool:
        current_pose = self._robot.get_current_position()
        if not current_pose or len(current_pose) < 6:
            raise RuntimeError(f"Failed to read current robot position during {label}")
        target_pose = [
            float(current_pose[0]) + float(dx_mm),
            float(current_pose[1]) + float(dy_mm),
            float(current_pose[2]),
            float(current_pose[3]),
            float(current_pose[4]),
            float(current_pose[5]),
        ]
        return self._move(target_pose, velocity, acceleration, label)

    def _compute_iterative_move(
        self,
        *,
        current_error_mm: float,
        correction_x_mm: float,
        correction_y_mm: float,
    ) -> tuple[float, float]:
        adaptive = self._calibration_settings.adaptive_movement
        min_step_mm = float(adaptive.min_step_mm)
        max_step_mm = float(adaptive.max_step_mm)
        recenter_alignment_threshold_mm = max(
            1e-6,
            float(getattr(self._calibration_settings.camera_tcp_offset, "recenter_alignment_threshold_mm", 0.5)),
        )
        target_error_mm = max(float(adaptive.target_error_mm), recenter_alignment_threshold_mm)
        max_error_ref = max(float(adaptive.max_error_ref), 1e-6)
        k = float(adaptive.k)

        normalized_error = min(current_error_mm / max_error_ref, 1.0)
        step_scale = math.tanh(k * normalized_error)
        max_move_mm = min_step_mm + step_scale * (max_step_mm - min_step_mm)

        if current_error_mm < target_error_mm * 2.0:
            damping_ratio = (current_error_mm / (target_error_mm * 2.0)) ** 2
            max_move_mm *= max(damping_ratio, 0.05)

        if current_error_mm < target_error_mm * 0.5:
            max_move_mm = min_step_mm

        magnitude = math.hypot(correction_x_mm, correction_y_mm)
        if magnitude > max_move_mm and magnitude > 1e-9:
            scale = max_move_mm / magnitude
        else:
            scale = 1.0
        return correction_x_mm * scale, correction_y_mm * scale

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

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Protocol

import numpy as np

from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.robot.configuration import RobotCalibrationSettings, RobotSettings
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
class _ZShiftSample:
    sample_index: int
    reference_z: float
    sample_z: float
    z_delta_mm: float
    marker_x_px: float
    marker_y_px: float
    image_dx_px: float
    image_dy_px: float
    local_dx_mm: float
    local_dy_mm: float


class CameraZShiftCalibrationService:
    _DEFAULT_ITERATIONS = 10
    _DEFAULT_Z_STEP_MM = -1.0
    _DEFAULT_SETTLE_TIME_S = 0.3
    _MARKER_AVG_FRAMES = 3

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

    def stop(self) -> None:
        self._stop_event.set()
        try:
            self._robot.stop_motion()
        except Exception:
            pass

    def calibrate(
        self,
        marker_id: int,
        samples: int,
        z_step_mm: float,
        settle_time_s: float,
    ) -> tuple[bool, str]:
        marker_id = int(marker_id)
        samples = max(1, int(samples))
        z_step_mm = float(z_step_mm)
        settle_time_s = max(0.0, float(settle_time_s))
        self._stop_event.clear()
        self._transformer.reload()
        if not self._transformer.is_available():
            return False, "Homography matrix not available"

        draw_contours_was_enabled = self._get_draw_contours_state()
        if draw_contours_was_enabled:
            self._vision.set_draw_contours(False)

        auto_brightness_locked = False
        auto_brightness_adjustment_locked = False
        try:
            if hasattr(self._vision, "get_auto_brightness_enabled") and self._vision.get_auto_brightness_enabled():
                if hasattr(self._vision, "lock_auto_brightness_region"):
                    auto_brightness_locked = bool(self._vision.lock_auto_brightness_region())
                if hasattr(self._vision, "lock_auto_brightness_adjustment"):
                    self._vision.lock_auto_brightness_adjustment()
                    auto_brightness_adjustment_locked = True

            if self._navigation is not None:
                ok = self._navigation.move_to_calibration_position(wait_cancelled=self._stop_event.is_set)
                if not ok:
                    return False, "Failed to move to calibration position"

            velocity = int(getattr(self._calibration_settings, "iterative_velocity", 20))
            acceleration = int(getattr(self._calibration_settings, "iterative_acceleration", 10))
            current_pose = self._robot.get_current_position()
            if not current_pose or len(current_pose) < 6:
                return False, "Current robot pose unavailable"

            target_z = float(getattr(self._calibration_settings, "z_target", current_pose[2]))
            initial_detection = self._detect_marker_center(marker_id, "initial target acquisition")
            if initial_detection is None:
                return False, f"Marker {marker_id} not detected for initial target acquisition"

            target_px, target_py = initial_detection
            target_x, target_y = self._transformer.transform(target_px, target_py)
            reference_pose = [
                target_x,
                target_y,
                target_z,
                float(current_pose[3]),
                float(current_pose[4]),
                float(current_pose[5]),
            ]
            if not self._move(reference_pose, velocity, acceleration, "reference pose"):
                return False, "Failed to move to reference marker-centered pose"

            if self._interruptible_sleep(settle_time_s):
                return False, "XY shift calibration stopped"

            baseline_detection = self._detect_marker_center(marker_id, "baseline detection")
            if baseline_detection is None:
                return False, f"Marker {marker_id} not detected at reference pose"
            baseline_px, baseline_py = baseline_detection

            image_cx = self._vision.get_camera_width() / 2.0
            image_cy = self._vision.get_camera_height() / 2.0
            x0, y0 = self._transformer.transform(image_cx, image_cy)
            x1, _ = self._transformer.transform(image_cx + 1.0, image_cy)
            _, y1 = self._transformer.transform(image_cx, image_cy + 1.0)
            local_scale_x = float(x1 - x0)
            local_scale_y = float(y1 - y0)

            _logger.info(
                "Starting camera Z-shift calibration: marker_id=%d reference_z=%.3f iterations=%d z_step_mm=%.3f",
                marker_id,
                target_z,
                samples,
                z_step_mm,
            )
            _logger.info(
                "Baseline marker center: x_pixels=(%.3f, %.3f) local_scale=(%.6f, %.6f) mm/px",
                baseline_px,
                baseline_py,
                local_scale_x,
                local_scale_y,
            )

            captured_samples: list[_ZShiftSample] = []
            for index in range(1, samples + 1):
                if self._stop_event.is_set():
                    return False, "XY shift calibration stopped"

                sample_z = target_z + index * z_step_mm
                sample_pose = [
                    reference_pose[0],
                    reference_pose[1],
                    sample_z,
                    reference_pose[3],
                    reference_pose[4],
                    reference_pose[5],
                ]
                if not self._move(sample_pose, velocity, acceleration, f"z sample {index}/{samples}"):
                    return False, f"Failed to move to Z sample {index}"
                if self._interruptible_sleep(settle_time_s):
                    return False, "XY shift calibration stopped"

                detection = self._detect_marker_center(marker_id, f"z sample {index}")
                if detection is None:
                    return False, f"Marker {marker_id} not detected at Z sample {index}"
                marker_px, marker_py = detection
                image_dx_px = float(marker_px - baseline_px)
                image_dy_px = float(marker_py - baseline_py)
                local_dx_mm = float(image_dx_px * local_scale_x)
                local_dy_mm = float(image_dy_px * local_scale_y)
                sample = _ZShiftSample(
                    sample_index=index,
                    reference_z=target_z,
                    sample_z=sample_z,
                    z_delta_mm=float(sample_z - target_z),
                    marker_x_px=float(marker_px),
                    marker_y_px=float(marker_py),
                    image_dx_px=image_dx_px,
                    image_dy_px=image_dy_px,
                    local_dx_mm=local_dx_mm,
                    local_dy_mm=local_dy_mm,
                )
                captured_samples.append(sample)
                _logger.info(
                    "Z-shift sample %d: z=%.3f dz=%.3f marker_px=(%.3f, %.3f) image_shift_px=(%.3f, %.3f) local_shift_mm=(%.6f, %.6f)",
                    index,
                    sample_z,
                    sample.z_delta_mm,
                    marker_px,
                    marker_py,
                    image_dx_px,
                    image_dy_px,
                    local_dx_mm,
                    local_dy_mm,
                )

            if not self._move(reference_pose, velocity, acceleration, "restore reference pose"):
                return False, "Failed to restore reference pose"

            z = np.array([s.z_delta_mm for s in captured_samples], dtype=np.float64)
            dx_px = np.array([s.image_dx_px for s in captured_samples], dtype=np.float64)
            dy_px = np.array([s.image_dy_px for s in captured_samples], dtype=np.float64)
            dx_mm = np.array([s.local_dx_mm for s in captured_samples], dtype=np.float64)
            dy_mm = np.array([s.local_dy_mm for s in captured_samples], dtype=np.float64)
            denom = float(np.dot(z, z))
            if denom <= 1e-9:
                return False, "Invalid Z sweep — zero denominator"

            x_shift_per_mm_z_px = float(np.dot(z, dx_px) / denom)
            y_shift_per_mm_z_px = float(np.dot(z, dy_px) / denom)
            x_shift_per_mm_z_mm = float(np.dot(z, dx_mm) / denom)
            y_shift_per_mm_z_mm = float(np.dot(z, dy_mm) / denom)

            self._robot_config.camera_z_shift_x_per_mm_px = x_shift_per_mm_z_px
            self._robot_config.camera_z_shift_y_per_mm_px = y_shift_per_mm_z_px
            self._robot_config.camera_z_shift_x_per_mm = x_shift_per_mm_z_mm
            self._robot_config.camera_z_shift_y_per_mm = y_shift_per_mm_z_mm
            self._settings.save(self._robot_config_key, self._robot_config)

            report_path = self._save_report(
                marker_id=marker_id,
                reference_pose=reference_pose,
                baseline_px=(baseline_px, baseline_py),
                local_scale=(local_scale_x, local_scale_y),
                samples=captured_samples,
                fit={
                    "x_shift_per_mm_z_px": x_shift_per_mm_z_px,
                    "y_shift_per_mm_z_px": y_shift_per_mm_z_px,
                    "x_shift_per_mm_z_mm": x_shift_per_mm_z_mm,
                    "y_shift_per_mm_z_mm": y_shift_per_mm_z_mm,
                },
            )
            _logger.info(
                self._format_terminal_report(
                    marker_id=marker_id,
                    reference_pose=reference_pose,
                    baseline_px=(baseline_px, baseline_py),
                    local_scale=(local_scale_x, local_scale_y),
                    samples=captured_samples,
                    fit={
                        "x_shift_per_mm_z_px": x_shift_per_mm_z_px,
                        "y_shift_per_mm_z_px": y_shift_per_mm_z_px,
                        "x_shift_per_mm_z_mm": x_shift_per_mm_z_mm,
                        "y_shift_per_mm_z_mm": y_shift_per_mm_z_mm,
                    },
                    report_path=report_path,
                )
            )

            return True, (
                f"XY shift calibrated for marker {marker_id}: "
                f"X/Z={x_shift_per_mm_z_mm:.6f} mm/mm, "
                f"Y/Z={y_shift_per_mm_z_mm:.6f} mm/mm"
                + (f", report={report_path}" if report_path else "")
            )
        finally:
            if draw_contours_was_enabled:
                self._vision.set_draw_contours(True)
            if auto_brightness_adjustment_locked and hasattr(self._vision, "unlock_auto_brightness_adjustment"):
                self._vision.unlock_auto_brightness_adjustment()
            if auto_brightness_locked and hasattr(self._vision, "unlock_auto_brightness_region"):
                self._vision.unlock_auto_brightness_region()

    def _save_report(
        self,
        *,
        marker_id: int,
        reference_pose: list[float],
        baseline_px: tuple[float, float],
        local_scale: tuple[float, float],
        samples: list[_ZShiftSample],
        fit: dict,
    ) -> str | None:
        try:
            base_dir = Path(self._vision.camera_to_robot_matrix_path).resolve().parent
            report_dir = base_dir / "z_shift_reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            report_path = report_dir / f"camera_z_shift_marker_{marker_id}_{timestamp}.json"
            payload = {
                "marker_id": int(marker_id),
                "reference_pose": [float(v) for v in reference_pose],
                "baseline_px": [float(baseline_px[0]), float(baseline_px[1])],
                "local_scale_mm_per_px": [float(local_scale[0]), float(local_scale[1])],
                "fit": {k: float(v) for k, v in fit.items()},
                "samples": [asdict(sample) for sample in samples],
            }
            with report_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            return str(report_path)
        except Exception as exc:
            _logger.warning("Failed to save camera Z-shift report: %s", exc)
            return None

    def _format_terminal_report(
        self,
        *,
        marker_id: int,
        reference_pose: list[float],
        baseline_px: tuple[float, float],
        local_scale: tuple[float, float],
        samples: list[_ZShiftSample],
        fit: dict,
        report_path: str | None,
    ) -> str:
        lines = [
            "=== CAMERA Z-SHIFT CALIBRATION REPORT ===",
            f"marker_id={int(marker_id)}",
            (
                "reference_pose="
                f"[{reference_pose[0]:.3f}, {reference_pose[1]:.3f}, {reference_pose[2]:.3f}, "
                f"{reference_pose[3]:.3f}, {reference_pose[4]:.3f}, {reference_pose[5]:.3f}]"
            ),
            f"baseline_px=({baseline_px[0]:.3f}, {baseline_px[1]:.3f})",
            f"local_scale_mm_per_px=({local_scale[0]:.6f}, {local_scale[1]:.6f})",
            (
                "fit: "
                f"x_shift_per_mm_z_px={float(fit['x_shift_per_mm_z_px']):.6f}, "
                f"y_shift_per_mm_z_px={float(fit['y_shift_per_mm_z_px']):.6f}, "
                f"x_shift_per_mm_z_mm={float(fit['x_shift_per_mm_z_mm']):.6f}, "
                f"y_shift_per_mm_z_mm={float(fit['y_shift_per_mm_z_mm']):.6f}"
            ),
            "samples:",
        ]
        for sample in samples:
            lines.append(
                "  "
                f"[{sample.sample_index:02d}] "
                f"z={sample.sample_z:.3f} dz={sample.z_delta_mm:.3f} "
                f"marker_px=({sample.marker_x_px:.3f}, {sample.marker_y_px:.3f}) "
                f"image_shift_px=({sample.image_dx_px:.3f}, {sample.image_dy_px:.3f}) "
                f"local_shift_mm=({sample.local_dx_mm:.6f}, {sample.local_dy_mm:.6f})"
            )
        if report_path:
            lines.append(f"report_path={report_path}")
        lines.append("========================================")
        return "\n".join(lines)

    def _detect_marker_center(self, marker_id: int, label: str) -> Optional[tuple[float, float]]:
        cfg = getattr(self._calibration_settings, "camera_tcp_offset", None)
        detection_attempts = int(getattr(cfg, "detection_attempts", 20))
        retry_delay_s = float(getattr(cfg, "retry_delay_s", 0.1))
        detections: list[tuple[float, float]] = []
        attempts = 0
        max_attempts = detection_attempts * self._MARKER_AVG_FRAMES
        while len(detections) < self._MARKER_AVG_FRAMES and attempts < max_attempts:
            attempts += 1
            if self._stop_event.is_set():
                return None
            frame = self._vision.get_latest_frame()
            if frame is None:
                self._interruptible_sleep(retry_delay_s)
                continue
            corners, ids, _ = self._vision.detect_aruco_markers(frame)
            if ids is None:
                self._interruptible_sleep(retry_delay_s)
                continue
            for detected_id, marker_corners in zip(ids.flatten(), corners):
                if int(detected_id) != marker_id:
                    continue
                center = marker_corners[0].mean(axis=0)
                detections.append((float(center[0]), float(center[1])))
                break
            else:
                self._interruptible_sleep(retry_delay_s)
        if not detections:
            return None
        return (
            float(np.mean([d[0] for d in detections])),
            float(np.mean([d[1] for d in detections])),
        )

    def _move(self, pose: list[float], velocity: int, acceleration: int, label: str) -> bool:
        _logger.info(
            "Camera Z-shift calibration move [%s]: pose=%s tool=%d user=%d vel=%d acc=%d",
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
        _logger.info("Camera Z-shift calibration move [%s] result=%s", label, ok)
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
        except Exception:
            return False

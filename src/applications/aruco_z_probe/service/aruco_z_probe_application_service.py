import logging
import threading
import time
from typing import Callable, List, Optional, Tuple

from src.applications.aruco_z_probe.service.i_aruco_z_probe_service import (
    ArucoZSample,
    IArucoZProbeService,
)

_logger = logging.getLogger(__name__)

_DEFAULT_VEL = 20
_DEFAULT_ACC = 20
_RETRY_DELAY = 0.1
_STABILIZATION_DELAY = 0.3


def _log(log_cb: Optional[Callable[[str], None]], msg: str) -> None:
    _logger.info(msg)
    if log_cb is not None:
        log_cb(msg)


class ArucoZProbeApplicationService(IArucoZProbeService):

    def __init__(
        self,
        navigation=None,
        robot_service=None,
        vision_service=None,
        robot_config=None,
    ):
        self._navigation = navigation
        self._robot = robot_service
        self._vision = vision_service
        self._robot_config = robot_config

    # ── IArucoZProbeService ──────────────────────────────────────────────

    def move_to_calibration_position(self) -> bool:
        if self._navigation is None:
            _logger.warning("move_to_calibration_position: navigation not available")
            return False
        try:
            return self._navigation.move_to_calibration_position()
        except Exception as exc:
            _logger.exception("move_to_calibration_position failed: %s", exc)
            return False

    def run_sweep(
        self,
        marker_id: int,
        min_z: float,
        sample_count: int,
        detection_attempts: int,
        stop_event: threading.Event,
        progress_cb: Callable[[int, int, float, Optional[float], Optional[float]], None],
        log_cb: Optional[Callable[[str], None]] = None,
        stabilization_delay: float = _STABILIZATION_DELAY,
    ) -> Tuple[bool, str, List[ArucoZSample]]:
        if self._robot is None or self._vision is None:
            return False, "Robot or vision service not available.", []

        try:
            pos = self._robot.get_current_position()  # [x, y, z, rx, ry, rz]
        except Exception as exc:
            return False, f"Failed to read robot position: {exc}", []

        x, y, baseline_z, rx, ry, rz = pos[0], pos[1], pos[2], pos[3], pos[4], pos[5]
        tool = int(getattr(self._robot_config, "robot_tool", 0)) if self._robot_config else 0
        user = int(getattr(self._robot_config, "robot_user", 0)) if self._robot_config else 0

        _log(log_cb, f"[DETECT] Detecting baseline at z={baseline_z:.2f} mm  (marker {marker_id}, up to {detection_attempts} attempts)")
        baseline_center = self._detect_marker(marker_id, detection_attempts, stop_event)
        if baseline_center is None:
            return False, f"Could not detect marker {marker_id} at baseline Z.", []

        baseline_x, baseline_y = baseline_center
        _log(log_cb, f"[DETECT] Baseline marker center: ({baseline_x:.2f}, {baseline_y:.2f}) px")

        step = (baseline_z - min_z) / max(sample_count, 1)
        samples: List[ArucoZSample] = []

        for i in range(1, sample_count + 1):
            if stop_event.is_set():
                self._return_to_baseline(x, y, baseline_z, rx, ry, rz, tool, user, log_cb)
                return False, "Sweep stopped by user.", samples

            z_target = baseline_z - i * step
            _log(log_cb, f"[MOVE]   Step {i}/{sample_count} → z={z_target:.2f} mm")

            try:
                self._robot.move_ptp(
                    position=[x, y, z_target, rx, ry, rz],
                    tool=tool,
                    user=user,
                    velocity=_DEFAULT_VEL,
                    acceleration=_DEFAULT_ACC,
                    wait_to_reach=True,
                )
            except Exception as exc:
                _logger.warning("move_ptp failed at step %d: %s", i, exc)
                _log(log_cb, f"[MOVE]   Move failed: {exc}")
                samples.append((z_target, None, None))
                progress_cb(i, sample_count, z_target, None, None)
                continue

            _log(log_cb, f"[MOVE]   Reached z={z_target:.2f} mm")
            _log(log_cb, f"[WAIT]   Stabilizing ({stabilization_delay:.2f}s)...")
            self._interruptible_sleep(stabilization_delay, stop_event)
            if stop_event.is_set():
                self._return_to_baseline(x, y, baseline_z, rx, ry, rz, tool, user, log_cb)
                return False, "Sweep stopped by user.", samples
            _log(log_cb, f"[DETECT] Detecting marker {marker_id}...")

            center = self._detect_marker(marker_id, detection_attempts, stop_event)
            if center is not None:
                dx = float(center[0] - baseline_x)
                dy = float(center[1] - baseline_y)
            else:
                dx, dy = None, None

            samples.append((z_target, dx, dy))
            progress_cb(i, sample_count, z_target, dx, dy)

        self._return_to_baseline(x, y, baseline_z, rx, ry, rz, tool, user, log_cb)
        return True, f"Sweep complete: {len(samples)} samples", samples

    def run_verification(
        self,
        z_heights: List[float],
        marker_id: int,
        detection_attempts: int,
        stop_event: threading.Event,
        progress_cb: Callable[[int, int, float, Optional[float], Optional[float]], None],
        log_cb: Optional[Callable[[str], None]] = None,
        stabilization_delay: float = _STABILIZATION_DELAY,
    ) -> Tuple[bool, str, List[ArucoZSample]]:
        if self._robot is None or self._vision is None:
            return False, "Robot or vision service not available.", []

        try:
            pos = self._robot.get_current_position()
        except Exception as exc:
            return False, f"Failed to read robot position: {exc}", []

        x, y, baseline_z, rx, ry, rz = pos[0], pos[1], pos[2], pos[3], pos[4], pos[5]
        tool = int(getattr(self._robot_config, "robot_tool", 0)) if self._robot_config else 0
        user = int(getattr(self._robot_config, "robot_user", 0)) if self._robot_config else 0

        _log(log_cb, f"[DETECT] Detecting baseline at z={baseline_z:.2f} mm  (marker {marker_id}, up to {detection_attempts} attempts)")
        baseline_center = self._detect_marker(marker_id, detection_attempts, stop_event)
        if baseline_center is None:
            return False, f"Could not detect marker {marker_id} at baseline Z for verification.", []

        baseline_x, baseline_y = baseline_center
        _log(log_cb, f"[DETECT] Baseline marker center: ({baseline_x:.2f}, {baseline_y:.2f}) px")

        samples: List[ArucoZSample] = []
        total = len(z_heights)

        for i, z_target in enumerate(z_heights, start=1):
            if stop_event.is_set():
                self._return_to_baseline(x, y, baseline_z, rx, ry, rz, tool, user, log_cb)
                return False, "Verification stopped by user.", samples

            _log(log_cb, f"[MOVE]   Point {i}/{total} → z={z_target:.2f} mm")

            try:
                self._robot.move_ptp(
                    position=[x, y, z_target, rx, ry, rz],
                    tool=tool,
                    user=user,
                    velocity=_DEFAULT_VEL,
                    acceleration=_DEFAULT_ACC,
                    wait_to_reach=True,
                )
            except Exception as exc:
                _logger.warning("Verification move_ptp failed at step %d: %s", i, exc)
                _log(log_cb, f"[MOVE]   Move failed: {exc}")
                samples.append((z_target, None, None))
                progress_cb(i, total, z_target, None, None)
                continue

            _log(log_cb, f"[MOVE]   Reached z={z_target:.2f} mm")
            _log(log_cb, f"[WAIT]   Stabilizing ({stabilization_delay:.2f}s)...")
            self._interruptible_sleep(stabilization_delay, stop_event)
            if stop_event.is_set():
                self._return_to_baseline(x, y, baseline_z, rx, ry, rz, tool, user, log_cb)
                return False, "Verification stopped by user.", samples
            _log(log_cb, f"[DETECT] Detecting marker {marker_id}...")

            center = self._detect_marker(marker_id, detection_attempts, stop_event)
            if center is not None:
                dx = float(center[0] - baseline_x)
                dy = float(center[1] - baseline_y)
            else:
                dx, dy = None, None

            samples.append((z_target, dx, dy))
            progress_cb(i, total, z_target, dx, dy)

        self._return_to_baseline(x, y, baseline_z, rx, ry, rz, tool, user, log_cb)
        return True, f"Verification complete: {len(samples)} points", samples

    # ── Helpers ──────────────────────────────────────────────────────────

    def _return_to_baseline(
        self, x: float, y: float, z: float, rx: float, ry: float, rz: float,
        tool: int, user: int,
        log_cb: Optional[Callable[[str], None]] = None,
    ) -> None:
        _log(log_cb, f"[MOVE]   Returning to baseline z={z:.2f} mm")
        try:
            self._robot.move_ptp(
                position=[x, y, z, rx, ry, rz],
                tool=tool,
                user=user,
                velocity=_DEFAULT_VEL,
                acceleration=_DEFAULT_ACC,
                wait_to_reach=True,
            )
            _log(log_cb, f"[MOVE]   Reached baseline z={z:.2f} mm")
        except Exception as exc:
            _logger.warning("Failed to return to baseline Z: %s", exc)
            _log(log_cb, f"[MOVE]   Return to baseline failed: {exc}")

    def _detect_marker(
        self,
        marker_id: int,
        attempts: int,
        stop_event: threading.Event,
        retry_delay: float = _RETRY_DELAY,
    ) -> Optional[Tuple[float, float]]:
        for attempt in range(1, attempts + 1):
            if stop_event.is_set():
                return None
            frame = self._vision.get_latest_frame()
            if frame is None:
                _logger.debug("No frame on attempt %d/%d", attempt, attempts)
                self._interruptible_sleep(retry_delay, stop_event)
                continue
            corners, ids, _ = self._vision.detect_aruco_markers(frame)
            if ids is None:
                _logger.debug("No ArUco markers on attempt %d/%d", attempt, attempts)
                self._interruptible_sleep(retry_delay, stop_event)
                continue
            flat_ids = ids.flatten() if hasattr(ids, "flatten") else ids
            for detected_id, marker_corners in zip(flat_ids, corners):
                if int(detected_id) != marker_id:
                    continue
                center = marker_corners[0].mean(axis=0)
                cx, cy = float(center[0]), float(center[1])
                _logger.debug(
                    "Detected marker %d at (%.3f, %.3f) on attempt %d/%d",
                    marker_id, cx, cy, attempt, attempts,
                )
                return cx, cy
            _logger.debug(
                "Marker %d not in frame on attempt %d/%d; seen=%s",
                marker_id, attempt, attempts, [int(i) for i in flat_ids],
            )
            self._interruptible_sleep(retry_delay, stop_event)
        return None

    @staticmethod
    def _interruptible_sleep(duration: float, stop_event: threading.Event) -> None:
        stop_event.wait(timeout=duration)

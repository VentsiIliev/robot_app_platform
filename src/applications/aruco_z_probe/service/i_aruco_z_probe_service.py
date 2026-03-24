import threading
from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Tuple

ArucoZSample = Tuple[float, Optional[float], Optional[float]]  # (z_mm, dx_px, dy_px)


class IArucoZProbeService(ABC):

    @abstractmethod
    def move_to_calibration_position(self) -> bool:
        """Move robot to the calibration group position."""

    @abstractmethod
    def run_sweep(
        self,
        marker_id: int,
        min_z: float,
        sample_count: int,
        detection_attempts: int,
        stop_event: threading.Event,
        progress_cb: Callable[[int, int, float, Optional[float], Optional[float]], None],
        log_cb: Optional[Callable[[str], None]] = None,
        stabilization_delay: float = 0.3,
    ) -> Tuple[bool, str, List[ArucoZSample]]:
        """
        Detect marker baseline at current Z, step down to min_z in sample_count
        equal steps, return to baseline Z at the end.
        progress_cb(step_index, total_steps, z_mm, dx_px, dy_px)
        log_cb(message) — optional, called for motion/detection status lines.
        Returns (success, message, samples).
        """

    @abstractmethod
    def run_verification(
        self,
        z_heights: List[float],
        marker_id: int,
        detection_attempts: int,
        stop_event: threading.Event,
        progress_cb: Callable[[int, int, float, Optional[float], Optional[float]], None],
        log_cb: Optional[Callable[[str], None]] = None,
        stabilization_delay: float = 0.3,
    ) -> Tuple[bool, str, List[ArucoZSample]]:
        """
        Re-detect baseline at current Z, then visit each z in z_heights,
        measure actual marker shift relative to that baseline, and return to
        the starting Z when done.
        progress_cb(step_index, total_steps, z_mm, dx_px, dy_px)
        log_cb(message) — optional, called for motion/detection status lines.
        Returns (success, message, samples).
        """

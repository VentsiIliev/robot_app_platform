import logging
import math
import threading
import time
from typing import Callable, List, Optional, Tuple

import numpy as np

from src.applications.aruco_z_probe.service.i_aruco_z_probe_service import (
    ArucoZSample,
    IArucoZProbeService,
)

_logger = logging.getLogger(__name__)


class StubArucoZProbeService(IArucoZProbeService):

    def move_to_calibration_position(self) -> bool:
        _logger.info("[Stub] move_to_calibration_position")
        return True

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
        _logger.info(
            "[Stub] run_sweep marker_id=%d min_z=%.1f sample_count=%d",
            marker_id, min_z, sample_count,
        )
        baseline_z = 300.0
        step = (baseline_z - min_z) / max(sample_count, 1)
        samples: List[ArucoZSample] = []

        for i in range(sample_count):
            if stop_event.is_set():
                return False, "Sweep stopped by user.", samples
            z = baseline_z - (i + 1) * step
            # Sinusoidal fake drift
            t = (i + 1) / sample_count
            dx = 5.0 * math.sin(2 * math.pi * t)
            dy = 3.0 * math.cos(2 * math.pi * t)
            samples.append((z, dx, dy))
            progress_cb(i + 1, sample_count, z, dx, dy)
            time.sleep(0.05)

        return True, f"Sweep complete: {len(samples)} samples", samples

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
        _logger.info("[Stub] run_verification %d points", len(z_heights))
        baseline_z = 819.37  # matches stub sweep baseline
        samples: List[ArucoZSample] = []
        total = len(z_heights)

        for i, z in enumerate(z_heights, start=1):
            if stop_event.is_set():
                return False, "Verification stopped by user.", samples
            # Sinusoidal drift + small noise
            t = (baseline_z - z) / max(baseline_z - min(z_heights), 1)
            dx = 5.0 * math.sin(2 * math.pi * t) + np.random.normal(0, 0.15)
            dy = 3.0 * math.cos(2 * math.pi * t) + np.random.normal(0, 0.10)
            samples.append((z, dx, dy))
            progress_cb(i, total, z, dx, dy)
            time.sleep(0.05)

        return True, f"Verification complete: {len(samples)} points", samples

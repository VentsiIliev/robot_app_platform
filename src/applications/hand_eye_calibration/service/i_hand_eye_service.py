from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np

HAND_EYE_PROGRESS_TOPIC = "HAND_EYE_PROGRESS"
HAND_EYE_COMPLETE_TOPIC = "HAND_EYE_COMPLETE"
HAND_EYE_SAMPLE_COUNT_TOPIC = "HAND_EYE_SAMPLE_COUNT"


@dataclass
class HandEyeConfig:
    chessboard_width: int = 17          # inner corner columns
    chessboard_height: int = 11         # inner corner rows
    square_size_mm: float = 15.0
    n_poses: int = 20                   # number of candidate poses to attempt
    rx_range_deg: float = 15.0          # ± rotation around X from home
    ry_range_deg: float = 15.0          # ± rotation around Y from home
    rz_range_deg: float = 15.0          # ± rotation around Z from home
    xy_range_mm: float = 60.0           # ± XY translation from home
    z_range_mm: float = 80.0            # ± Z translation from home
    stabilization_delay_s: float = 1.0       # delay after main pose moves / before sample capture
    servo_stabilization_delay_s: float = 0.2  # delay after servo/search intermediate moves
    velocity: int = 20
    acceleration: int = 10
    probe_dx_mm: float = 15.0           # probe distance for Jacobian X estimation
    probe_dy_mm: float = 15.0           # probe distance for Jacobian Y estimation
    probe_dz_mm: float = 15.0           # probe distance for Jacobian Z estimation (scale)
    probe_rotations: bool = True        # also probe Rx/Ry/Rz for a full 2×6 Jacobian
    probe_drx_deg: float = 8.0          # probe angle for Jacobian RX estimation
    probe_dry_deg: float = 8.0          # probe angle for Jacobian RY estimation
    probe_drz_deg: float = 8.0          # probe angle for Jacobian RZ estimation
    servo_tol_px: int = 40              # pixel radius considered "centred enough"
    servo_max_iter: int = 8             # max visual-servo iterations per pose
    servo_max_step_mm: float = 25.0     # clip per-iteration correction to this
    feedforward_max_step_mm: float = 20.0  # hard cap on feedforward pre-correction
    search_radius_mm: float = 50.0      # max XY search radius in nearby-board search


class IHandEyeCalibrationService(ABC):

    @abstractmethod
    def start_capture(self) -> None:
        """Start automated pose collection and calibration in a background thread."""

    @abstractmethod
    def stop_capture(self) -> None:
        """Request the background thread to stop."""

    @abstractmethod
    def is_running(self) -> bool:
        """Return True while the background thread is alive."""

    @abstractmethod
    def get_latest_annotated_frame(self) -> Optional[np.ndarray]:
        """Return the latest camera frame with detected chessboard corners overlaid."""

    @abstractmethod
    def get_config(self) -> HandEyeConfig:
        """Return the current configuration."""

    @abstractmethod
    def save_config(self, config: HandEyeConfig) -> None:
        """Persist a new configuration."""

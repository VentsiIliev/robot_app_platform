from __future__ import annotations

import cv2
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

INTRINSIC_CAPTURE_PROGRESS_TOPIC = "INTRINSIC_CAPTURE_PROGRESS"

# Available ArUco dictionaries exposed in the UI
ARUCO_DICT_OPTIONS = {
    "4x4_50":   cv2.aruco.DICT_4X4_50,
    "4x4_100":  cv2.aruco.DICT_4X4_100,
    "4x4_250":  cv2.aruco.DICT_4X4_250,
    "4x4_1000": cv2.aruco.DICT_4X4_1000,
    "5x5_50":   cv2.aruco.DICT_5X5_50,
    "5x5_100":  cv2.aruco.DICT_5X5_100,
    "5x5_250":  cv2.aruco.DICT_5X5_250,
    "6x6_250":  cv2.aruco.DICT_6X6_250,
}


@dataclass
class IntrinsicCaptureConfig:
    # Board type
    board_type: str = "chessboard"          # "chessboard" or "charuco"
    # Board parameters (must match the physical board)
    chessboard_width: int = 0               # chessboard: inner corner cols | charuco: square cols (0 = from vision service)
    chessboard_height: int = 0              # chessboard: inner corner rows | charuco: square rows (0 = from vision service)
    square_size_mm: float = 0.0            # square size in mm (0 = from vision service)
    # CharuCo-specific
    aruco_dict: str = "4x4_250"            # ArUco dictionary name (see ARUCO_DICT_OPTIONS)
    marker_size_mm: float = 0.0            # ArUco marker size in mm (0 = auto: square_size × 0.75)
    # Acquisition parameters
    grid_rows: int = 3
    grid_cols: int = 3
    margin_px: float = 60.0
    tilt_deg: float = 5.0
    z_delta_mm: float = 40.0
    probe_dx_mm: float = 20.0
    probe_dy_mm: float = 20.0
    probe_drx_deg: float = 3.0             # roll probe angle for tilt sensitivity (0 = skip)
    probe_dry_deg: float = 3.0             # pitch probe angle for tilt sensitivity (0 = skip)
    probe_drz_deg: float = 0.0             # yaw probe angle for tilt sensitivity (0 = skip)
    # ChArUco sweep mode (replaces Jacobian+servo when board_type == "charuco")
    charuco_sweep_x_mm: float = 100.0     # half-range: sweeps -x … +x around home
    charuco_sweep_y_mm: float = 100.0
    charuco_min_corners: int = 6          # minimum detected corners to accept a frame
    charuco_rz_deg: float = 15.0          # ±yaw angle added at each grid position (0 = skip)
    charuco_compute_hand_eye: bool = True  # auto-compute hand-eye after intrinsic calibration
    velocity: int = 20
    acceleration: int = 10
    stabilization_delay_s: float = 0.5
    max_detection_retries: int = 1
    initial_detection_attempts: int = 5
    initial_detection_delay_s: float = 1.0
    output_dir: str = field(default="")


class IIntrinsicCaptureService(ABC):

    @abstractmethod
    def start_capture(self) -> None: ...

    @abstractmethod
    def stop_capture(self) -> None: ...

    @abstractmethod
    def is_running(self) -> bool: ...

    @abstractmethod
    def get_latest_frame(self) -> Optional[np.ndarray]: ...

    @abstractmethod
    def get_config(self) -> IntrinsicCaptureConfig: ...

    @abstractmethod
    def save_config(self, config: IntrinsicCaptureConfig) -> None: ...

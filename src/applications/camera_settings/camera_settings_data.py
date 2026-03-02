from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class CameraSettingsData:
    # Core
    index:                    int   = 0
    width:                    int   = 1280
    height:                   int   = 720
    skip_frames:              int   = 30
    capture_position_offset:  int   = -4

    # Detection
    contour_detection:        bool  = True
    draw_contours:            bool  = True
    threshold:                int   = 150
    threshold_pickup_area:    int   = 200
    epsilon:                  float = 0.05
    min_contour_area:         float = 1000.0
    max_contour_area:         float = 10_000_000.0

    # Preprocessing
    gaussian_blur:            bool  = True
    blur_kernel_size:         int   = 3
    threshold_type:           str   = "binary_inv"
    dilate_enabled:           bool  = True
    dilate_kernel_size:       int   = 3
    dilate_iterations:        int   = 2
    erode_enabled:            bool  = True
    erode_kernel_size:        int   = 3
    erode_iterations:         int   = 4

    # Calibration
    chessboard_width:         int   = 32
    chessboard_height:        int   = 20
    square_size_mm:           float = 25.0
    calibration_skip_frames:  int   = 30

    # Brightness
    brightness_auto:          bool  = True
    brightness_kp:            float = 0.0
    brightness_ki:            float = 0.2
    brightness_kd:            float = 0.05
    target_brightness:        float = 200.0
    # Brightness area points are set via camera preview — not a schema widget
    brightness_area_points: List[Tuple[int, int]] = field(default_factory=list)

    # ArUco
    aruco_enabled:            bool  = False
    aruco_dictionary:         str   = "DICT_4X4_1000"
    aruco_flip_image:         bool  = False

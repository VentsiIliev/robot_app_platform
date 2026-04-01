from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import numpy as np


class IVisionService(ABC):

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def set_raw_mode(self, enabled: bool) -> None: ...

    @abstractmethod
    def capture_calibration_image(self) -> tuple[bool, str]: ...

    @abstractmethod
    def calibrate_camera(self) -> tuple[bool, str]: ...

    @abstractmethod
    def update_settings(self, settings: dict) -> tuple[bool, str]: ...

    @abstractmethod
    def save_work_area(self, area_type: str, pixel_points: List[Tuple[int, int]]) -> tuple[bool, str]: ...

    @abstractmethod
    def get_latest_contours(self) -> list: ...

    @abstractmethod
    def get_work_area(self, area_type: str) -> tuple[bool, str, any]: ...

    @abstractmethod
    def run_matching(self, workpieces: list, contours: list) -> Tuple[dict, int, List, List]: ...

    @abstractmethod
    def get_latest_frame(self)-> np.ndarray: ...

    @abstractmethod
    def get_latest_corrected_frame(self) -> np.ndarray | None: ...

    @abstractmethod
    def detect_aruco_markers(self, image: np.ndarray) -> tuple: ...

    @abstractmethod
    def get_camera_width(self) -> int: ...

    @abstractmethod
    def get_camera_height(self) -> int: ...

    @abstractmethod
    def get_chessboard_width(self) -> int: ...

    @abstractmethod
    def get_chessboard_height(self) -> int: ...

    @abstractmethod
    def get_square_size_mm(self) -> float: ...

    @abstractmethod
    def set_draw_contours(self, enabled: bool) -> None: ...

    @abstractmethod
    def get_auto_brightness_enabled(self) -> bool: ...

    @abstractmethod
    def set_auto_brightness_enabled(self, enabled: bool) -> None: ...

    @abstractmethod
    def lock_auto_brightness_region(self) -> bool: ...

    @abstractmethod
    def unlock_auto_brightness_region(self) -> None: ...

    @abstractmethod
    def lock_auto_brightness_adjustment(self) -> None: ...

    @abstractmethod
    def unlock_auto_brightness_adjustment(self) -> None: ...

    @property
    @abstractmethod
    def camera_to_robot_matrix_path(self) -> str: ...

    @abstractmethod
    def set_active_work_area(self, area_id: str | None) -> None:
        """Switch the active work area used by vision."""

    @abstractmethod
    def set_detection_area(self, area: str) -> None:
        """Compatibility wrapper for switching the active work area."""

    @abstractmethod
    def get_capture_pos_offset(self) -> float: ...

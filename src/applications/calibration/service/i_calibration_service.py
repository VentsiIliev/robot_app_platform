from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Sequence
import numpy as np
from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.intrinsic_calibration_capture.service.i_intrinsic_capture_service import IntrinsicCaptureConfig
from src.applications.height_measuring.service.i_height_measuring_app_service import LaserDetectionResult
from src.shared_contracts.declarations import WorkAreaDefinition


@dataclass(frozen=True)
class RobotCalibrationPreview:
    ok: bool
    message: str
    frame: np.ndarray | None = None
    available_ids: list[int] | None = None
    selected_ids: list[int] | None = None
    report: dict | None = None


class ICalibrationService(ABC):
    @abstractmethod
    def load_calibration_settings(self) -> CalibrationSettingsData | None: ...

    @abstractmethod
    def save_calibration_settings(self, settings: CalibrationSettingsData) -> None: ...

    @abstractmethod
    def capture_calibration_image(self) -> tuple[bool, str]: ...

    @abstractmethod
    def calibrate_camera(self) -> tuple[bool, str]: ...

    @abstractmethod
    def get_intrinsic_capture_config(self) -> IntrinsicCaptureConfig: ...

    @abstractmethod
    def save_intrinsic_capture_config(self, config: IntrinsicCaptureConfig) -> None: ...

    @abstractmethod
    def start_intrinsic_auto_capture(self) -> tuple[bool, str]: ...

    @abstractmethod
    def stop_intrinsic_auto_capture(self) -> None: ...

    @abstractmethod
    def is_intrinsic_auto_capture_running(self) -> bool: ...

    @abstractmethod
    def calibrate_robot(self) -> tuple[bool, str]: ...

    @abstractmethod
    def preview_robot_calibration(self) -> RobotCalibrationPreview: ...

    @abstractmethod
    def calibrate_camera_and_robot(self) -> tuple[bool, str]: ...

    @abstractmethod
    def calibrate_camera_tcp_offset(self) -> tuple[bool, str]: ...

    @abstractmethod
    def calibrate_laser(self) -> tuple[bool, str]: ...

    @abstractmethod
    def detect_laser_once(self) -> LaserDetectionResult: ...

    @abstractmethod
    def stop_calibration(self) -> None: ...

    @abstractmethod
    def is_calibrated(self) -> bool: ...

    @abstractmethod
    def test_calibration(self, model_name: str = "homography") -> tuple[bool, str]: ...

    @abstractmethod
    def stop_test_calibration(self) -> None: ...

    @abstractmethod
    def measure_marker_heights(self) -> tuple[bool, str]: ...

    @abstractmethod
    def get_work_area_definitions(self) -> list[WorkAreaDefinition]: ...

    @abstractmethod
    def get_active_work_area_id(self) -> str: ...

    @abstractmethod
    def set_active_work_area_id(self, area_id: str) -> None: ...

    @abstractmethod
    def save_height_mapping_area(
        self,
        area_key: str,
        corners_norm: Sequence[tuple[float, float]],
    ) -> tuple[bool, str]: ...

    @abstractmethod
    def get_height_mapping_area(self, area_key: str) -> list[tuple[float, float]]: ...

    @abstractmethod
    def generate_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> list[tuple[float, float]]: ...

    @abstractmethod
    def measure_area_grid(
        self,
        area_id: str,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> tuple[bool, str]: ...

    @abstractmethod
    def verify_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
        progress_callback: Callable[[str, str, int, int], None] | None = None,
    ) -> tuple[bool, str, dict]: ...

    @abstractmethod
    def ensure_active_work_area_observed(self) -> tuple[bool, str]: ...

    @abstractmethod
    def stop_marker_height_measurement(self) -> None: ...

    @abstractmethod
    def can_measure_marker_heights(self) -> bool: ...

    @abstractmethod
    def verify_height_model(self, area_id: str = "") -> tuple[bool, str]: ...

    @abstractmethod
    def get_height_calibration_data(self, area_id: str = ""): ...

    @abstractmethod
    def has_saved_height_model(self, area_id: str = "") -> bool: ...

    @abstractmethod
    def restore_pending_safety_walls(self) -> bool: ...

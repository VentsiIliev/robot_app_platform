from abc import ABC, abstractmethod
from typing import Sequence


class ICalibrationService(ABC):

    @abstractmethod
    def capture_calibration_image(self) -> tuple[bool, str]: ...

    @abstractmethod
    def calibrate_camera(self) -> tuple[bool, str]: ...

    @abstractmethod
    def calibrate_robot(self) -> tuple[bool, str]: ...

    @abstractmethod
    def calibrate_camera_and_robot(self) -> tuple[bool, str]: ...

    @abstractmethod
    def calibrate_camera_tcp_offset(self) -> tuple[bool, str]: ...

    @abstractmethod
    def stop_calibration(self) -> None: ...

    @abstractmethod
    def is_calibrated(self) -> bool: ...

    @abstractmethod
    def test_calibration(self) -> tuple[bool, str]: ...

    @abstractmethod
    def stop_test_calibration(self) -> None: ...

    @abstractmethod
    def measure_marker_heights(self) -> tuple[bool, str]: ...

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
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> tuple[bool, str]: ...

    @abstractmethod
    def stop_marker_height_measurement(self) -> None: ...

    @abstractmethod
    def can_measure_marker_heights(self) -> bool: ...

    @abstractmethod
    def verify_height_model(self) -> tuple[bool, str]: ...

    @abstractmethod
    def get_height_calibration_data(self): ...

    @abstractmethod
    def has_saved_height_model(self) -> bool: ...

    @abstractmethod
    def restore_pending_safety_walls(self) -> bool: ...

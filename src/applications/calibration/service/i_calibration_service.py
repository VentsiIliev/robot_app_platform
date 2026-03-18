from abc import ABC, abstractmethod


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
    def get_height_calibration_data(self): ...

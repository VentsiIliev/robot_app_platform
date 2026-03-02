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
from abc import ABC, abstractmethod


class IRobotCalibrationService(ABC):

    @abstractmethod
    def run_calibration(self) -> tuple[bool, str]: ...

    @abstractmethod
    def stop_calibration(self) -> None: ...

    @abstractmethod
    def is_calibrated(self) -> bool: ...

    @abstractmethod
    def get_status(self) -> str: ...
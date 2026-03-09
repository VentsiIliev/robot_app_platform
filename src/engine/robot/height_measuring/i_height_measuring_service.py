from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.engine.robot.height_measuring.laser_calibration_data import LaserCalibrationData


class IHeightMeasuringService(ABC):

    @abstractmethod
    def measure_at(self, x: float, y: float) -> Optional[float]: ...

    @abstractmethod
    def is_calibrated(self) -> bool: ...

    @abstractmethod
    def get_calibration_data(self) -> Optional["LaserCalibrationData"]: ...

    @abstractmethod
    def reload_calibration(self) -> None: ...


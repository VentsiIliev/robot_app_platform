from abc import ABC, abstractmethod
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.engine.robot.height_measuring.laser_calibration_data import LaserCalibrationData
    from src.engine.robot.height_measuring.depth_map_data import DepthMapData


class IHeightMeasuringService(ABC):

    @abstractmethod
    def measure_at(self, x: float, y: float) -> Optional[float]: ...

    @abstractmethod
    def is_calibrated(self) -> bool: ...

    @abstractmethod
    def get_calibration_data(self) -> Optional["LaserCalibrationData"]: ...

    @abstractmethod
    def reload_calibration(self) -> None: ...

    @abstractmethod
    def save_height_map(self, samples: List[List[float]]) -> None: ...

    @abstractmethod
    def get_depth_map_data(self) -> Optional["DepthMapData"]: ...


from abc import ABC, abstractmethod
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.engine.robot.height_measuring.laser_calibration_data import LaserCalibrationData
    from src.engine.robot.height_measuring.depth_map_data import DepthMapData


class IHeightMeasuringService(ABC):

    @abstractmethod
    def begin_measurement_session(self) -> None: ...

    @abstractmethod
    def end_measurement_session(self) -> None: ...

    @abstractmethod
    def measure_at(self, x: float, y: float, *, already_at_xy: bool = False) -> Optional[float]: ...

    @abstractmethod
    def is_calibrated(self) -> bool: ...

    @abstractmethod
    def get_calibration_data(self) -> Optional["LaserCalibrationData"]: ...

    @abstractmethod
    def reload_calibration(self) -> None: ...

    @abstractmethod
    def save_height_map(
        self,
        samples: List[List[float]],
        area_id: str = "",
        marker_ids: Optional[List[int]] = None,
        point_labels: Optional[List[str]] = None,
        grid_rows: int = 0,
        grid_cols: int = 0,
        planned_points: Optional[List[List[float]]] = None,
        planned_point_labels: Optional[List[str]] = None,
        unavailable_point_labels: Optional[List[str]] = None,
    ) -> None: ...

    @abstractmethod
    def get_depth_map_data(self, area_id: str = "") -> Optional["DepthMapData"]: ...

from abc import ABC, abstractmethod
from typing import List, Optional

from src.engine.core.i_health_checkable import IHealthCheckable
from src.shared_contracts.events.weight_events import CellState, WeightReading
from src.robot_systems.glue.settings.cells import CalibrationConfig


class IWeightCellService(IHealthCheckable, ABC):

    @abstractmethod
    def connect(self, cell_id: int) -> bool: ...

    @abstractmethod
    def disconnect(self, cell_id: int) -> None: ...

    @abstractmethod
    def connect_all(self) -> None: ...

    @abstractmethod
    def disconnect_all(self) -> None: ...

    @abstractmethod
    def read_weight(self, cell_id: int) -> Optional[WeightReading]: ...

    @abstractmethod
    def get_cell_state(self, cell_id: int) -> CellState: ...

    @abstractmethod
    def get_connected_cell_ids(self) -> List[int]: ...

    @abstractmethod
    def start_monitoring(self, cell_ids: List[int], interval_s: float = 0.5) -> None: ...

    @abstractmethod
    def stop_monitoring(self) -> None: ...

    @abstractmethod
    def tare(self, cell_id: int) -> bool: ...

    @abstractmethod
    def get_calibration(self, cell_id: int) -> Optional[CalibrationConfig]: ...

    @abstractmethod
    def update_offset(self, cell_id: int, offset: float) -> bool: ...

    @abstractmethod
    def update_scale(self, cell_id: int, scale: float) -> bool: ...

    @abstractmethod
    def update_config(self, cell_id: int, offset: float, scale: float) -> bool: ...

    def is_healthy(self) -> bool:
        """Healthy = at least one cell is connected."""
        return len(self.get_connected_cell_ids()) > 0

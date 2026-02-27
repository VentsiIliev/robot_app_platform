from abc import ABC, abstractmethod
from typing import List

from src.engine.hardware.weight.config import CellsConfig


class IGlueCellSettingsService(ABC):

    @abstractmethod
    def load_cells(self) -> CellsConfig: ...

    @abstractmethod
    def save_cells(self, config: CellsConfig) -> None: ...

    @abstractmethod
    def tare(self, cell_id: int) -> bool: ...

    @abstractmethod
    def get_cell_ids(self) -> List[int]: ...

    @abstractmethod
    def push_calibration(self, cell_id: int, offset: float, scale: float) -> bool:
        """Push offset + scale to the physical hardware (ESP32 server)."""
        ...

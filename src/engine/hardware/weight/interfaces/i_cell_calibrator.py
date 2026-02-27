from abc import ABC, abstractmethod

from src.robot_systems.glue.settings.cells import CalibrationConfig


class ICellCalibrator(ABC):
    """
    Responsible for calibration operations on a single cell.
    Decoupled from transport — calibration is a separate concern.
    """

    @abstractmethod
    def tare(self, cell_id: int) -> bool: ...

    @abstractmethod
    def get_config(self, cell_id: int) -> CalibrationConfig: ...

    @abstractmethod
    def update_offset(self, cell_id: int, offset: float) -> bool: ...

    @abstractmethod
    def update_scale(self, cell_id: int, scale: float) -> bool: ...

    @abstractmethod
    def update_config(self, cell_id: int, offset: float, scale: float) -> bool: ...
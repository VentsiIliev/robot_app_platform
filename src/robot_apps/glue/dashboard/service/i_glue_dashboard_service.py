from abc import abstractmethod
from typing import Dict, List, Optional

from src.engine.process.i_process import IProcess


class IGlueDashboardService(IProcess):
    """
    start / stop / pause / resume / reset_errors — inherited from IProcess.
    Subclasses must implement all abstract methods here AND in IProcess.
    """

    @abstractmethod
    def clean(self) -> None: ...

    @abstractmethod
    def set_mode(self, mode: str) -> None: ...

    @abstractmethod
    def change_glue(self, cell_id: int, glue_type: str) -> None: ...

    @abstractmethod
    def get_cell_capacity(self, cell_id: int) -> float: ...

    @abstractmethod
    def get_cell_glue_type(self, cell_id: int) -> Optional[str]: ...

    @abstractmethod
    def get_all_glue_types(self) -> List[str]: ...

    @abstractmethod
    def get_initial_cell_state(self, cell_id: int) -> Optional[Dict]: ...

    @abstractmethod
    def get_cells_count(self) -> int: ...

    @abstractmethod
    def get_cell_connection_state(self, cell_id: int) -> str: ...

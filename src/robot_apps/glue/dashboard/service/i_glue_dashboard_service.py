from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class IGlueDashboardService(ABC):

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def pause(self) -> None: ...

    @abstractmethod
    def clean(self) -> None: ...

    @abstractmethod
    def reset_errors(self) -> None: ...

    @abstractmethod
    def set_mode(self, mode: str) -> None: ...

    @abstractmethod
    def change_glue(self, cell_id: int, glue_type: str) -> None: ...

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

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
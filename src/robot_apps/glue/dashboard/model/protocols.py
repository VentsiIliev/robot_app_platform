from __future__ import annotations
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class CellStateManagerProtocol(Protocol):
    def get_cell_state(self, cell_id: int) -> Optional[str]: ...


@runtime_checkable
class CellWeightMonitorProtocol(Protocol):
    def get_cell_weight(self, cell_id: int) -> Optional[float]: ...
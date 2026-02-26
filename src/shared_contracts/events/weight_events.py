from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class CellState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING   = "connecting"
    CONNECTED    = "connected"
    ERROR        = "error"


@dataclass(frozen=True)
class WeightReading:
    cell_id:   int
    value:     float
    unit:      str      = "g"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_valid(self, min_threshold: float, max_threshold: float) -> bool:
        return min_threshold <= self.value <= max_threshold


@dataclass(frozen=True)
class CellStateEvent:
    cell_id:   int
    state:     CellState
    message:   str      = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WeightTopics:

    @staticmethod
    def state(cell_id: int) -> str:
        return f"weight/cell/{cell_id}/state"

    @staticmethod
    def reading(cell_id: int) -> str:
        return f"weight/cell/{cell_id}/reading"

    @staticmethod
    def all_readings() -> str:
        return "weight/cell/all/reading"
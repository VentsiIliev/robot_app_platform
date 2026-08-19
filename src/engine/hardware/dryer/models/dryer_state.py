from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from src.engine.hardware.dryer.models.dryer_commands import DryerStatus


@dataclass(frozen=True)
class DryerState:
    raw_status: int = 0
    is_ready: bool = False
    servos_moving: bool = False
    plate_on_position: bool = False
    is_healthy: bool = False
    communication_errors: List[str] = field(default_factory=list)

    @classmethod
    def from_raw_status(cls, raw_status: int) -> "DryerState":
        status = DryerStatus(raw_status)
        return cls(
            raw_status=raw_status,
            is_ready=bool(status & DryerStatus.READY),
            servos_moving=bool(status & DryerStatus.SERVOS_MOVING),
            plate_on_position=bool(status & DryerStatus.PLATE_ON_POSITION),
            is_healthy=True,
        )

    @property
    def has_errors(self) -> bool:
        return bool(self.communication_errors)

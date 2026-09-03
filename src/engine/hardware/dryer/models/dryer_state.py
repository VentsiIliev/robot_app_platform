from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Mapping

from src.engine.hardware.dryer.models.dryer_status import dryer_statuses


@dataclass(frozen=True)
class DryerState:
    raw_status: int = 0
    is_ready: bool = False
    ejecting: bool = False
    eject_done: bool = False
    next_position_moving: bool = False
    next_position_done: bool = False
    is_healthy: bool = False
    communication_errors: List[str] = field(default_factory=list)

    @classmethod
    def from_raw_status(
        cls,
        raw_status: int,
        statuses: Mapping[str, int] | None = None,
    ) -> "DryerState":
        masks = dryer_statuses(statuses)
        return cls(
            raw_status=raw_status,
            is_ready=bool(raw_status & masks["ready"]),
            ejecting=bool(raw_status & masks["eject"]),
            eject_done=bool(raw_status & masks["eject_done"]),
            next_position_moving=bool(raw_status & masks["next_pos_moving"]),
            next_position_done=bool(raw_status & masks["next_pos_done"]),
            is_healthy=True,
        )

    @property
    def servos_moving(self) -> bool:
        """Compatibility view of either firmware movement status."""
        return self.ejecting or self.next_position_moving

    @property
    def plate_on_position(self) -> bool:
        """Compatibility view of the firmware's completed-position status."""
        return self.next_position_done

    @property
    def has_errors(self) -> bool:
        return bool(self.communication_errors)

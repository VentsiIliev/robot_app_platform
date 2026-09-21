from __future__ import annotations

import math
from dataclasses import dataclass

from src.engine.robot.motion_sequence import OrderedMotionType


@dataclass(frozen=True)
class NextCycleTarget:
    """Validated robot target used to preposition for the next paint cycle."""

    group_id: str
    position: tuple[float, ...]
    velocity_percent: float
    acceleration_percent: float
    motion_type: OrderedMotionType

    def __post_init__(self) -> None:
        group_id = str(self.group_id).strip()
        position = tuple(float(value) for value in self.position)
        if not group_id:
            raise ValueError("next-cycle target requires a movement group ID")
        if len(position) != 6 or not all(math.isfinite(value) for value in position):
            raise ValueError("next-cycle target requires six finite position values")
        object.__setattr__(self, "group_id", group_id)
        object.__setattr__(self, "position", position)
        object.__setattr__(
            self,
            "motion_type",
            OrderedMotionType.parse(self.motion_type, field_name="next_cycle_target.motion_type"),
        )

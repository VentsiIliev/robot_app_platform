from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.engine.robot.configuration import MovementGroup


class MovementGroupType(Enum):
    SINGLE_POSITION = "single_position"
    MULTI_POSITION = "multi_position"
    VELOCITY_ONLY = "velocity_only"


@dataclass(frozen=True)
class MovementGroupDefinition:
    id: str
    group_type: MovementGroupType
    label: str = ""
    has_iterations: bool = False
    has_trajectory_execution: bool = False
    removable: bool = False

    def __post_init__(self) -> None:
        if not self.label:
            object.__setattr__(self, "label", self.id)

    def build_default_group(self) -> MovementGroup:
        return MovementGroup(
            has_iterations=self.has_iterations,
            has_trajectory_execution=self.has_trajectory_execution,
        )

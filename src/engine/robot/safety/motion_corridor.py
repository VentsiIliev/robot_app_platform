from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class MotionCorridor:
    """A bounded Cartesian tunnel for explicitly constrained linear motion."""

    corridor_id: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    entry_z_max: float
    maximum_velocity: float
    maximum_acceleration: float
    allow_planar_transit: bool = False

    def validate(self) -> None:
        if not str(self.corridor_id).strip():
            raise ValueError("Motion corridor requires a non-empty corridor_id")
        if self.x_min >= self.x_max or self.y_min >= self.y_max:
            raise ValueError("Motion corridor XY bounds must have positive area")
        if not self.allow_planar_transit and self.z_min >= 0.0:
            raise ValueError("Motion corridor z_min must be below zero")
        if self.z_min >= self.entry_z_max:
            raise ValueError("Motion corridor Z bounds must have positive height")
        if self.entry_z_max < 0.0:
            raise ValueError("Motion corridor entry_z_max must be at or above zero")
        if self.maximum_velocity <= 0.0 or self.maximum_acceleration <= 0.0:
            raise ValueError("Motion corridor velocity and acceleration limits must be positive")

    def contains_xy(self, pose: list[float]) -> bool:
        return (
            len(pose) >= 2
            and self.x_min <= float(pose[0]) <= self.x_max
            and self.y_min <= float(pose[1]) <= self.y_max
        )

    def contains_xyz(self, pose: list[float]) -> bool:
        return (
            len(pose) >= 3
            and self.contains_xy(pose)
            and self.z_min <= float(pose[2]) <= self.entry_z_max
        )


class MotionCorridorRegistry:
    """Thread-safe registry of installation-specific reusable motion corridors."""

    def __init__(self) -> None:
        self._corridors: dict[str, MotionCorridor] = {}
        self._lock = RLock()

    def register(self, corridor: MotionCorridor) -> None:
        corridor.validate()
        with self._lock:
            self._corridors[corridor.corridor_id] = corridor

    def get(self, corridor_id: str) -> MotionCorridor | None:
        with self._lock:
            return self._corridors.get(str(corridor_id).strip())

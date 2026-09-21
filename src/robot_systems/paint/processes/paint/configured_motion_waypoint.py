from __future__ import annotations

from dataclasses import dataclass

from src.engine.robot.motion_sequence import OrderedMotionType


@dataclass(frozen=True)
class ConfiguredMotionWaypoint:
    """Validated six-axis waypoint and its complete motion profile."""

    position: tuple[float, float, float, float, float, float]
    velocity_percent: float
    acceleration_percent: float
    motion_type: OrderedMotionType
    blend_radius: float

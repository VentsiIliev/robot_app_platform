from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


MotionType = Literal["linear", "ptp"]


@dataclass(frozen=True)
class MotionSequenceSegment:
    """One explicitly parameterized robot motion segment."""

    position: list[float]
    velocity: float
    acceleration: float
    motion_type: MotionType = "linear"
    blend_radius: float = 0.0

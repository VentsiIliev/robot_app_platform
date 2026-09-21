from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaintContactCommandJob:
    """Motion settings for one generated paint-contact path."""

    job_index: int
    pattern_type: str
    velocity_percent: float
    acceleration_percent: float

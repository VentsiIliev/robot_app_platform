from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class GlueOverlayTopics:
    JOB_LOADED = "glue/overlay/job_loaded"


@dataclass(frozen=True)
class GlueOverlaySegment:
    path_index: int
    workpiece_id: str
    pattern_type: str
    segment_index: int
    points: list[tuple[float, float]]


@dataclass(frozen=True)
class GlueOverlayJobLoadedEvent:
    image: Any
    image_width: int
    image_height: int
    segments: list[GlueOverlaySegment]


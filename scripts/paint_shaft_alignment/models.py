from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from .region import PixelRegion


PixelPoint = Tuple[float, float]


class MarkerDetectionStatus(str, Enum):
    DETECTED = "detected"
    FRAME_UNAVAILABLE = "frame_unavailable"
    DETECTION_FAILED = "detection_failed"
    MARKER_NOT_FOUND = "marker_not_found"
    DUPLICATE_MARKER_ID = "duplicate_marker_id"


@dataclass(frozen=True)
class ShaftMarkerConfig:
    marker_id: int
    minimum_area_px2: float = 0.0

    def __post_init__(self) -> None:
        if self.marker_id < 0:
            raise ValueError("marker_id must be non-negative")
        if self.minimum_area_px2 < 0.0:
            raise ValueError("minimum_area_px2 must be non-negative")


@dataclass(frozen=True)
class DetectedMarker:
    marker_id: int
    corners_px: Tuple[PixelPoint, ...]
    center_px: PixelPoint
    area_px2: float
    orientation_deg: float
    orientation_samples: Tuple[Tuple[str, float], ...] = ()
    orientation_diagnostics: Tuple[Tuple[str, float], ...] = ()


@dataclass(frozen=True)
class MarkerDetection:
    status: MarkerDetectionStatus
    detected_at_monotonic_s: float
    marker_id: int
    detected_ids: Tuple[int, ...] = ()
    detected_markers: Tuple[DetectedMarker, ...] = ()
    detection_region: PixelRegion | None = None
    corners_px: Tuple[PixelPoint, ...] = ()
    center_px: PixelPoint | None = None
    area_px2: float | None = None
    orientation_deg: float | None = None
    message: str = ""

    @property
    def detected(self) -> bool:
        return self.status is MarkerDetectionStatus.DETECTED

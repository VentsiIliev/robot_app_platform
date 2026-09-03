"""Standalone paint-shaft alignment experiments.

The package intentionally depends on platform interfaces while keeping all
shaft-specific semantics outside the paint robot system until they are stable.
"""

from .detector import ShaftMarkerDetector
from .models import DetectedMarker, MarkerDetection, MarkerDetectionStatus, ShaftMarkerConfig

__all__ = [
    "DetectedMarker",
    "MarkerDetection",
    "MarkerDetectionStatus",
    "ShaftMarkerConfig",
    "ShaftMarkerDetector",
]

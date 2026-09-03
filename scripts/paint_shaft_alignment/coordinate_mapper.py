from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import MarkerDetection


class PixelToRobotTransformer(Protocol):
    def is_available(self) -> bool: ...

    def transform(self, x: float, y: float) -> tuple[float, float]: ...


@dataclass(frozen=True)
class MarkerRobotPosition:
    available: bool
    x_mm: float | None = None
    y_mm: float | None = None
    message: str = ""


class MarkerCenterRobotMapper:
    """Map a detected marker center to paint calibration/base robot XY."""

    def __init__(self, transformer: PixelToRobotTransformer) -> None:
        self._transformer = transformer

    def map(self, detection: MarkerDetection) -> MarkerRobotPosition:
        if not detection.detected or detection.center_px is None:
            return MarkerRobotPosition(False, message="Marker center is unavailable.")
        return self.map_center(detection.center_px)

    def map_center(self, center_px: tuple[float, float]) -> MarkerRobotPosition:
        if not self._transformer.is_available():
            return MarkerRobotPosition(False, message="Paint vision calibration is unavailable.")
        try:
            x_mm, y_mm = self._transformer.transform(*center_px)
        except Exception as exc:
            return MarkerRobotPosition(False, message=f"Pixel-to-robot conversion failed: {exc}")
        return MarkerRobotPosition(
            True,
            x_mm=float(x_mm),
            y_mm=float(y_mm),
            message="Marker center mapped to paint calibration coordinates.",
        )

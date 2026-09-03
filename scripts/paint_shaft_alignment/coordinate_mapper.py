from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

from .models import MarkerDetection


class PixelToRobotTransformer(Protocol):
    def is_available(self) -> bool: ...

    def transform(self, x: float, y: float) -> tuple[float, float]: ...


class CameraToTcpTransformer(Protocol):
    def is_available(self) -> bool: ...

    def transform_to_tcp(self, x: float, y: float) -> tuple[float, float]: ...


class TcpCoordinateTransformer:
    """Expose camera-to-TCP conversion through the mapper's transform contract."""

    def __init__(self, transformer: CameraToTcpTransformer) -> None:
        self._transformer = transformer

    def is_available(self) -> bool:
        return self._transformer.is_available()

    def transform(self, x: float, y: float) -> tuple[float, float]:
        return self._transformer.transform_to_tcp(x, y)


class CapturePoseCompensatedTransformer:
    """Shift calibrated coordinates by the capture-pose translation."""

    def __init__(
        self,
        transformer: PixelToRobotTransformer,
        calibration_pose: tuple[float, float, float, float, float, float],
        capture_pose: tuple[float, float, float, float, float, float],
    ) -> None:
        self._transformer = transformer
        self._dx = float(capture_pose[0]) - float(calibration_pose[0])
        self._dy = float(capture_pose[1]) - float(calibration_pose[1])

    @property
    def translation_xy_mm(self) -> tuple[float, float]:
        return self._dx, self._dy

    def is_available(self) -> bool:
        return self._transformer.is_available()

    def transform(self, x: float, y: float) -> tuple[float, float]:
        transformed_x, transformed_y = self._transformer.transform(x, y)
        return transformed_x + self._dx, transformed_y + self._dy


@dataclass(frozen=True)
class MarkerRobotPosition:
    available: bool
    x_mm: float | None = None
    y_mm: float | None = None
    message: str = ""


@dataclass(frozen=True)
class MarkerPlanarSize:
    available: bool
    real_size_mm: float
    width_mm: float | None = None
    height_mm: float | None = None
    width_difference_mm: float | None = None
    height_difference_mm: float | None = None
    message: str = ""


class MarkerCenterRobotMapper:
    """Map a marker center through an injected robot-coordinate transform."""

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
            message="Marker center mapped to robot coordinates.",
        )

    def measure_planar_size(
        self,
        corners_px: tuple[tuple[float, float], ...],
        real_size_mm: float,
    ) -> MarkerPlanarSize:
        if len(corners_px) != 4:
            return MarkerPlanarSize(False, real_size_mm, message="Four marker corners are required.")
        if not self._transformer.is_available():
            return MarkerPlanarSize(False, real_size_mm, message="Paint vision calibration is unavailable.")
        try:
            corners_mm = [self._transformer.transform(*corner) for corner in corners_px]
        except Exception as exc:
            return MarkerPlanarSize(False, real_size_mm, message=f"Marker-size conversion failed: {exc}")

        def distance(first, second) -> float:
            return math.hypot(second[0] - first[0], second[1] - first[1])

        width = (distance(corners_mm[0], corners_mm[1]) + distance(corners_mm[3], corners_mm[2])) / 2.0
        height = (distance(corners_mm[1], corners_mm[2]) + distance(corners_mm[0], corners_mm[3])) / 2.0
        return MarkerPlanarSize(
            True,
            real_size_mm=float(real_size_mm),
            width_mm=width,
            height_mm=height,
            width_difference_mm=width - real_size_mm,
            height_difference_mm=height - real_size_mm,
            message="Marker size measured on the calibrated homography plane.",
        )

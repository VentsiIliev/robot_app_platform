from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class AlignmentReference:
    x_mm: float
    y_mm: float
    orientation_deg: float
    marker_width_mm: float
    marker_height_mm: float


@dataclass(frozen=True)
class AlignmentMisalignment:
    available: bool
    dx_mm: float | None = None
    dy_mm: float | None = None
    orientation_difference_deg: float | None = None
    marker_width_difference_mm: float | None = None
    marker_height_difference_mm: float | None = None
    message: str = ""


@dataclass(frozen=True)
class MisalignmentThresholds:
    dx_mm: float
    dy_mm: float
    orientation_deg: float
    marker_width_mm: float
    marker_height_mm: float

    def exceeded_by(self, value: AlignmentMisalignment) -> tuple[str, ...]:
        if not value.available:
            return ()
        checks = (
            ("dX", value.dx_mm, self.dx_mm),
            ("dY", value.dy_mm, self.dy_mm),
            ("dRZ", value.orientation_difference_deg, self.orientation_deg),
            ("dW", value.marker_width_difference_mm, self.marker_width_mm),
            ("dH", value.marker_height_difference_mm, self.marker_height_mm),
        )
        return tuple(
            name
            for name, measured, threshold in checks
            if measured is not None and abs(measured) > threshold
        )


class AlignmentReferenceCapture:
    """Collect a robust reference and compare subsequent marker observations."""

    def __init__(self, required_samples: int) -> None:
        if required_samples <= 0:
            raise ValueError("Reference sample count must be positive")
        self._required_samples = required_samples
        self._samples: list[tuple[float, float, float, float, float]] = []
        self._reference: AlignmentReference | None = None
        self._capturing = False

    @property
    def required_samples(self) -> int:
        return self._required_samples

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    @property
    def capturing(self) -> bool:
        return self._capturing

    @property
    def reference(self) -> AlignmentReference | None:
        return self._reference

    def start(self) -> None:
        self._samples.clear()
        self._reference = None
        self._capturing = True

    def record(
        self,
        x_mm: float,
        y_mm: float,
        orientation_deg: float,
        marker_width_mm: float,
        marker_height_mm: float,
    ) -> bool:
        if not self._capturing:
            return False
        self._samples.append(
            (
                float(x_mm),
                float(y_mm),
                float(orientation_deg),
                float(marker_width_mm),
                float(marker_height_mm),
            )
        )
        if len(self._samples) < self._required_samples:
            return False
        self._reference = AlignmentReference(
            x_mm=statistics.median(sample[0] for sample in self._samples),
            y_mm=statistics.median(sample[1] for sample in self._samples),
            orientation_deg=self._circular_mean(sample[2] for sample in self._samples),
            marker_width_mm=statistics.median(sample[3] for sample in self._samples),
            marker_height_mm=statistics.median(sample[4] for sample in self._samples),
        )
        self._capturing = False
        return True

    def compare(
        self,
        x_mm: float,
        y_mm: float,
        orientation_deg: float,
        marker_width_mm: float,
        marker_height_mm: float,
    ) -> AlignmentMisalignment:
        if self._reference is None:
            return AlignmentMisalignment(False, message="Reference not captured.")
        return AlignmentMisalignment(
            True,
            dx_mm=float(x_mm) - self._reference.x_mm,
            dy_mm=float(y_mm) - self._reference.y_mm,
            orientation_difference_deg=self._shortest_angle(
                float(orientation_deg) - self._reference.orientation_deg
            ),
            marker_width_difference_mm=(
                float(marker_width_mm) - self._reference.marker_width_mm
            ),
            marker_height_difference_mm=(
                float(marker_height_mm) - self._reference.marker_height_mm
            ),
            message="Misalignment relative to captured reference.",
        )

    @staticmethod
    def _circular_mean(values) -> float:
        radians = [math.radians(float(value)) for value in values]
        return AlignmentReferenceCapture._shortest_angle(
            math.degrees(
                math.atan2(
                    sum(math.sin(value) for value in radians),
                    sum(math.cos(value) for value in radians),
                )
            )
        )

    @staticmethod
    def _shortest_angle(angle: float) -> float:
        return (float(angle) + 180.0) % 360.0 - 180.0

from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass

from .models import DetectedMarker, PixelPoint


@dataclass(frozen=True)
class StableMarkerEstimate:
    stable: bool
    sample_count: int
    required_samples: int
    center_px: PixelPoint | None = None
    orientation_deg: float | None = None
    center_spread_px: float | None = None
    orientation_spread_deg: float | None = None
    message: str = ""


class MarkerSampleStabilizer:
    """Produce a robust marker estimate from a rolling sample window."""

    def __init__(
        self,
        *,
        required_samples: int,
        maximum_center_spread_px: float,
        maximum_orientation_spread_deg: float,
        misses_before_reset: int,
    ) -> None:
        if required_samples <= 0 or misses_before_reset <= 0:
            raise ValueError("Sample and miss counts must be positive")
        if maximum_center_spread_px < 0.0 or maximum_orientation_spread_deg < 0.0:
            raise ValueError("Spread limits must be non-negative")
        self._required_samples = required_samples
        self._maximum_center_spread = maximum_center_spread_px
        self._maximum_orientation_spread = maximum_orientation_spread_deg
        self._misses_before_reset = misses_before_reset
        self._samples: deque[DetectedMarker] = deque(maxlen=required_samples)
        self._misses = 0

    def record_detection(self, marker: DetectedMarker) -> StableMarkerEstimate:
        self._samples.append(marker)
        self._misses = 0
        return self.estimate()

    def record_miss(self) -> StableMarkerEstimate:
        self._misses += 1
        if self._misses >= self._misses_before_reset:
            self.reset()
        return self.estimate()

    def reset(self) -> None:
        self._samples.clear()
        self._misses = 0

    def estimate(self) -> StableMarkerEstimate:
        count = len(self._samples)
        if count == 0:
            return StableMarkerEstimate(
                False,
                0,
                self._required_samples,
                message="No valid marker samples.",
            )

        center_x = statistics.median(sample.center_px[0] for sample in self._samples)
        center_y = statistics.median(sample.center_px[1] for sample in self._samples)
        center_spread = max(
            math.hypot(sample.center_px[0] - center_x, sample.center_px[1] - center_y)
            for sample in self._samples
        )
        orientation = self._circular_mean_deg(
            sample.orientation_deg for sample in self._samples
        )
        orientation_spread = max(
            abs(self._shortest_angle_deg(sample.orientation_deg - orientation))
            for sample in self._samples
        )

        enough_samples = count >= self._required_samples
        spread_ok = (
            center_spread <= self._maximum_center_spread
            and orientation_spread <= self._maximum_orientation_spread
        )
        stable = enough_samples and spread_ok
        if not enough_samples:
            message = f"Collecting marker samples ({count}/{self._required_samples})."
        elif not spread_ok:
            message = "Marker samples exceed stability spread limits."
        else:
            message = "Marker estimate is stable."
        return StableMarkerEstimate(
            stable=stable,
            sample_count=count,
            required_samples=self._required_samples,
            center_px=(float(center_x), float(center_y)),
            orientation_deg=orientation,
            center_spread_px=center_spread,
            orientation_spread_deg=orientation_spread,
            message=message,
        )

    @staticmethod
    def _circular_mean_deg(values) -> float:
        radians = [math.radians(float(value)) for value in values]
        angle = math.degrees(
            math.atan2(
                sum(math.sin(value) for value in radians),
                sum(math.cos(value) for value in radians),
            )
        )
        return MarkerSampleStabilizer._shortest_angle_deg(angle)

    @staticmethod
    def _shortest_angle_deg(angle: float) -> float:
        return (float(angle) + 180.0) % 360.0 - 180.0

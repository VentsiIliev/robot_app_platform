from __future__ import annotations

import math
from enum import Enum

from .models import DetectedMarker
from .region import DetectionRegionProvider, PixelRegion


class TrackingState(str, Enum):
    SEARCHING = "searching"
    TRACKING = "tracking"
    RECOVERING = "recovering"


class MarkerRegionTracker:
    """Stateful ROI tracker; independent from ArUco detection."""

    def __init__(
        self,
        base_region_provider: DetectionRegionProvider,
        *,
        padding_px: int,
        minimum_width_px: int,
        minimum_height_px: int,
        recovery_expansion_px: int,
        misses_before_fallback: int,
        detections_before_tracking: int,
        acquisition_misses_before_reset: int,
        position_filter_alpha: float,
        prediction_gain: float,
        maximum_center_jump_px: float,
        maximum_area_ratio_change: float,
    ) -> None:
        if min(padding_px, recovery_expansion_px) < 0:
            raise ValueError("Tracker padding and recovery expansion must be non-negative")
        if min(
            minimum_width_px,
            minimum_height_px,
            misses_before_fallback,
            detections_before_tracking,
            acquisition_misses_before_reset,
        ) <= 0:
            raise ValueError("Tracker dimensions and miss limit must be positive")
        if not 0.0 < position_filter_alpha <= 1.0:
            raise ValueError("position_filter_alpha must be in (0, 1]")
        if not 0.0 <= prediction_gain <= 1.0:
            raise ValueError("prediction_gain must be in [0, 1]")
        if maximum_center_jump_px <= 0.0:
            raise ValueError("maximum_center_jump_px must be positive")
        if maximum_area_ratio_change <= 1.0:
            raise ValueError("maximum_area_ratio_change must be greater than 1")
        self._base = base_region_provider
        self._padding = padding_px
        self._minimum_width = minimum_width_px
        self._minimum_height = minimum_height_px
        self._recovery_expansion = recovery_expansion_px
        self._miss_limit = misses_before_fallback
        self._detections_before_tracking = detections_before_tracking
        self._acquisition_miss_limit = acquisition_misses_before_reset
        self._alpha = position_filter_alpha
        self._prediction_gain = prediction_gain
        self._maximum_center_jump = maximum_center_jump_px
        self._maximum_area_ratio_change = maximum_area_ratio_change
        self.reset()

    @property
    def state(self) -> TrackingState:
        return self._state

    @property
    def consecutive_misses(self) -> int:
        return self._misses

    def region_for_frame(self, image_width: int, image_height: int) -> PixelRegion:
        if self._region is None:
            return self._base.resolve(image_width, image_height)
        return self._clip(self._region, image_width, image_height)

    def record_detection(self, marker: DetectedMarker) -> bool:
        measured_x, measured_y = marker.center_px
        if not self._measurement_is_plausible(marker):
            return False
        if self._filtered_center is None:
            filtered = (measured_x, measured_y)
            velocity = (0.0, 0.0)
        else:
            previous_x, previous_y = self._filtered_center
            filtered = (
                previous_x + self._alpha * (measured_x - previous_x),
                previous_y + self._alpha * (measured_y - previous_y),
            )
            velocity = (filtered[0] - previous_x, filtered[1] - previous_y)
        self._filtered_center = filtered
        self._velocity = velocity
        self._last_area = marker.area_px2
        self._consecutive_detections += 1
        self._acquisition_misses = 0

        if self._consecutive_detections < self._detections_before_tracking:
            self._misses = 0
            self._state = TrackingState.SEARCHING
            return True

        xs = [point[0] for point in marker.corners_px]
        ys = [point[1] for point in marker.corners_px]
        marker_width = max(xs) - min(xs)
        marker_height = max(ys) - min(ys)
        width = max(self._minimum_width, math.ceil(marker_width + 2 * self._padding))
        height = max(self._minimum_height, math.ceil(marker_height + 2 * self._padding))
        predicted_x = filtered[0] + self._prediction_gain * velocity[0]
        predicted_y = filtered[1] + self._prediction_gain * velocity[1]
        self._region = PixelRegion(
            x=round(predicted_x - width / 2),
            y=round(predicted_y - height / 2),
            width=width,
            height=height,
        )
        self._misses = 0
        self._state = TrackingState.TRACKING
        return True

    def record_miss(self) -> None:
        if self._region is None:
            self._acquisition_misses += 1
            if self._acquisition_misses >= self._acquisition_miss_limit:
                self._consecutive_detections = 0
                self._acquisition_misses = 0
            return
        self._consecutive_detections = 0
        self._misses += 1
        if self._misses >= self._miss_limit:
            self.reset()
            return
        amount = self._recovery_expansion
        self._region = PixelRegion(
            self._region.x - amount,
            self._region.y - amount,
            self._region.width + 2 * amount,
            self._region.height + 2 * amount,
        )
        self._state = TrackingState.RECOVERING

    def reset(self) -> None:
        self._region: PixelRegion | None = None
        self._filtered_center: tuple[float, float] | None = None
        self._velocity = (0.0, 0.0)
        self._last_area: float | None = None
        self._consecutive_detections = 0
        self._acquisition_misses = 0
        self._misses = 0
        self._state = TrackingState.SEARCHING

    @staticmethod
    def _clip(region: PixelRegion, image_width: int, image_height: int) -> PixelRegion:
        left = min(max(0, region.x), max(0, image_width - 1))
        top = min(max(0, region.y), max(0, image_height - 1))
        right = min(image_width, max(left + 1, region.right))
        bottom = min(image_height, max(top + 1, region.bottom))
        return PixelRegion(left, top, right - left, bottom - top)

    def _measurement_is_plausible(self, marker: DetectedMarker) -> bool:
        if self._filtered_center is not None:
            dx = marker.center_px[0] - self._filtered_center[0]
            dy = marker.center_px[1] - self._filtered_center[1]
            if math.hypot(dx, dy) > self._maximum_center_jump:
                return False
        if self._last_area is not None and self._last_area > 0.0:
            ratio = marker.area_px2 / self._last_area
            limit = self._maximum_area_ratio_change
            if ratio > limit or ratio < 1.0 / limit:
                return False
        return True

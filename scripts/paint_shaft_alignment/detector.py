from __future__ import annotations

import logging
import time
from typing import Callable, Protocol

import numpy as np

from .models import (
    DetectedMarker,
    MarkerDetection,
    MarkerDetectionStatus,
    PixelPoint,
    ShaftMarkerConfig,
)
from .region import PixelRegion
from .orientation import CornerEdgeOrientationStrategy, MarkerOrientationStrategy


class VisionMarkerSource(Protocol):
    """Small seam implemented by the platform's IVisionService."""

    def get_latest_frame(self) -> np.ndarray: ...

    def detect_aruco_markers(self, image: np.ndarray) -> tuple: ...


class ShaftMarkerDetector:
    """Detect one configured shaft marker in a frame.

    This milestone intentionally reports image-space geometry only. Robot-frame
    pose estimation belongs in a later component once timestamped frame/robot
    pose synchronization is available.
    """

    def __init__(
        self,
        vision: VisionMarkerSource,
        config: ShaftMarkerConfig,
        *,
        orientation_strategy: MarkerOrientationStrategy | None = None,
        clock: Callable[[], float] = time.monotonic,
        logger: logging.Logger | None = None,
    ) -> None:
        self._vision = vision
        self._config = config
        self._orientation_strategy = orientation_strategy or CornerEdgeOrientationStrategy()
        self._clock = clock
        self._logger = logger or logging.getLogger(__name__)

    def detect(
        self,
        frame: np.ndarray | None = None,
        detection_region: PixelRegion | None = None,
    ) -> MarkerDetection:
        detected_at = self._clock()
        try:
            source_frame = frame if frame is not None else self._vision.get_latest_frame()
        except Exception as exc:
            self._logger.exception("Could not read the latest camera frame")
            return self._result(
                MarkerDetectionStatus.FRAME_UNAVAILABLE,
                detected_at,
                message=f"Could not read the latest camera frame: {exc}",
            )
        if not self._is_valid_frame(source_frame):
            return self._result(
                MarkerDetectionStatus.FRAME_UNAVAILABLE,
                detected_at,
                message="No camera frame is available.",
            )

        detection_frame = source_frame
        if detection_region is not None:
            detection_frame = source_frame[
                detection_region.y:detection_region.bottom,
                detection_region.x:detection_region.right,
            ]

        try:
            corners, ids, _processed_frame = self._vision.detect_aruco_markers(detection_frame)
        except Exception as exc:
            self._logger.exception("Shaft marker detection failed")
            return self._result(
                MarkerDetectionStatus.DETECTION_FAILED,
                detected_at,
                detection_region=detection_region,
                message=f"ArUco detector failed: {exc}",
            )

        try:
            normalized_ids = self._normalize_ids(ids)
            if corners is None:
                corners = []
        except (TypeError, ValueError) as exc:
            return self._result(
                MarkerDetectionStatus.DETECTION_FAILED,
                detected_at,
                detection_region=detection_region,
                message=f"ArUco detector returned invalid IDs: {exc}",
            )
        if len(corners) != len(normalized_ids):
            return self._result(
                MarkerDetectionStatus.DETECTION_FAILED,
                detected_at,
                detected_ids=normalized_ids,
                detection_region=detection_region,
                message="ArUco detector returned mismatched corners and IDs.",
            )

        detected_markers = self._build_marker_observations(
            corners,
            normalized_ids,
            detection_region,
        )
        if detected_markers is None:
            return self._result(
                MarkerDetectionStatus.DETECTION_FAILED,
                detected_at,
                detected_ids=normalized_ids,
                detection_region=detection_region,
                message="One or more detected markers have invalid corner geometry.",
            )

        matching_indexes = [
            index for index, marker_id in enumerate(normalized_ids)
            if marker_id == self._config.marker_id
        ]
        if not matching_indexes:
            return self._result(
                MarkerDetectionStatus.MARKER_NOT_FOUND,
                detected_at,
                detected_ids=normalized_ids,
                detected_markers=detected_markers,
                detection_region=detection_region,
                message=f"Shaft marker {self._config.marker_id} was not detected.",
            )
        if len(matching_indexes) > 1:
            return self._result(
                MarkerDetectionStatus.DUPLICATE_MARKER_ID,
                detected_at,
                detected_ids=normalized_ids,
                detected_markers=detected_markers,
                detection_region=detection_region,
                message=f"Marker ID {self._config.marker_id} appeared more than once.",
            )

        target = detected_markers[matching_indexes[0]]
        marker_corners = target.corners_px
        area = target.area_px2
        if area < self._config.minimum_area_px2:
            return self._result(
                MarkerDetectionStatus.MARKER_NOT_FOUND,
                detected_at,
                detected_ids=normalized_ids,
                detected_markers=detected_markers,
                detection_region=detection_region,
                corners_px=marker_corners,
                area_px2=area,
                message=(
                    f"Shaft marker area {area:.1f} px^2 is below the configured "
                    f"minimum {self._config.minimum_area_px2:.1f} px^2."
                ),
            )

        return self._result(
            MarkerDetectionStatus.DETECTED,
            detected_at,
            detected_ids=normalized_ids,
            detected_markers=detected_markers,
            detection_region=detection_region,
            corners_px=marker_corners,
            center_px=target.center_px,
            area_px2=area,
            orientation_deg=target.orientation_deg,
            message=f"Shaft marker {self._config.marker_id} detected.",
        )

    def _result(
        self,
        status: MarkerDetectionStatus,
        detected_at: float,
        *,
        detected_ids: tuple[int, ...] = (),
        detected_markers: tuple[DetectedMarker, ...] = (),
        detection_region: PixelRegion | None = None,
        corners_px: tuple[PixelPoint, ...] = (),
        center_px: PixelPoint | None = None,
        area_px2: float | None = None,
        orientation_deg: float | None = None,
        message: str,
    ) -> MarkerDetection:
        return MarkerDetection(
            status=status,
            detected_at_monotonic_s=detected_at,
            marker_id=self._config.marker_id,
            detected_ids=detected_ids,
            detected_markers=detected_markers,
            detection_region=detection_region,
            corners_px=corners_px,
            center_px=center_px,
            area_px2=area_px2,
            orientation_deg=orientation_deg,
            message=message,
        )

    @staticmethod
    def _is_valid_frame(frame: object) -> bool:
        return isinstance(frame, np.ndarray) and frame.size > 0

    @staticmethod
    def _normalize_ids(ids: object) -> tuple[int, ...]:
        if ids is None:
            return ()
        return tuple(int(value) for value in np.asarray(ids).reshape(-1))

    @staticmethod
    def _normalize_corners(corners: object) -> tuple[PixelPoint, ...] | None:
        values = np.asarray(corners, dtype=float).reshape(-1, 2)
        if values.shape != (4, 2) or not np.isfinite(values).all():
            return None
        return tuple((float(x), float(y)) for x, y in values)

    def _build_marker_observations(
        self,
        corners: object,
        marker_ids: tuple[int, ...],
        region: PixelRegion | None,
    ) -> tuple[DetectedMarker, ...] | None:
        observations = []
        for marker_id, raw_corners in zip(marker_ids, corners):
            try:
                normalized = self._normalize_corners(raw_corners)
            except (TypeError, ValueError):
                return None
            if normalized is None:
                return None
            offset_x = float(region.x) if region is not None else 0.0
            offset_y = float(region.y) if region is not None else 0.0
            normalized = tuple(
                (x + offset_x, y + offset_y) for x, y in normalized
            )
            center = (
                sum(point[0] for point in normalized) / 4.0,
                sum(point[1] for point in normalized) / 4.0,
            )
            try:
                orientation = self._orientation_strategy.estimate(normalized)
                observations.append(
                    DetectedMarker(
                        marker_id=marker_id,
                        corners_px=normalized,
                        center_px=center,
                        area_px2=abs(self._signed_polygon_area(normalized)),
                        orientation_deg=orientation.primary_deg,
                        orientation_samples=orientation.samples,
                        orientation_diagnostics=orientation.diagnostics,
                    )
                )
            except Exception:
                self._logger.exception("Marker orientation strategy failed for ID %s", marker_id)
                return None
        return tuple(observations)



    @staticmethod
    def _signed_polygon_area(points: tuple[PixelPoint, ...]) -> float:
        return 0.5 * sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
        )

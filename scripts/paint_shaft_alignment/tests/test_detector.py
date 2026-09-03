from __future__ import annotations

import unittest

import numpy as np

from scripts.paint_shaft_alignment.detector import ShaftMarkerDetector
from scripts.paint_shaft_alignment.models import DetectedMarker, MarkerDetectionStatus, ShaftMarkerConfig
from scripts.paint_shaft_alignment.region import (
    CenteredDetectionRegionProvider,
    PixelRegion,
    SelectableDetectionRegionProvider,
)
from scripts.paint_shaft_alignment.tracker import MarkerRegionTracker, TrackingState


class _FakeVision:
    def __init__(self, *, frame=None, corners=None, ids=None, error=None):
        self.frame = frame
        self.corners = [] if corners is None else corners
        self.ids = ids
        self.error = error
        self.detected_image_shape = None

    def get_latest_frame(self):
        return self.frame

    def detect_aruco_markers(self, image):
        self.detected_image_shape = image.shape
        if self.error is not None:
            raise self.error
        return self.corners, self.ids, image


class SelectableDetectionRegionProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = SelectableDetectionRegionProvider(
            CenteredDetectionRegionProvider(width=40, height=20)
        )

    def test_uses_centered_default_until_region_is_drawn(self) -> None:
        self.assertEqual(PixelRegion(30, 40, 40, 20), self.provider.resolve(100, 100))

    def test_normalizes_reverse_drag_and_clips_to_frame(self) -> None:
        self.assertTrue(self.provider.select((90, 80), (-10, 20)))
        self.assertEqual(PixelRegion(0, 20, 80, 60), self.provider.resolve(80, 100))

    def test_ignores_zero_area_selection_and_can_restore_default(self) -> None:
        self.assertFalse(self.provider.select((10, 10), (10, 30)))
        self.assertTrue(self.provider.select((10, 10), (30, 30)))
        self.provider.clear()
        self.assertEqual(PixelRegion(30, 40, 40, 20), self.provider.resolve(100, 100))


class ShaftMarkerDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = np.zeros((100, 120, 3), dtype=np.uint8)
        self.marker = np.array(
            [[[10.0, 20.0], [30.0, 20.0], [30.0, 40.0], [10.0, 40.0]]],
            dtype=np.float32,
        )

    def test_reports_target_marker_geometry(self) -> None:
        vision = _FakeVision(
            frame=self.frame,
            corners=[self.marker],
            ids=np.array([[17]], dtype=np.int32),
        )
        detector = ShaftMarkerDetector(
            vision,
            ShaftMarkerConfig(marker_id=17),
            clock=lambda: 12.5,
        )

        result = detector.detect()

        self.assertEqual(MarkerDetectionStatus.DETECTED, result.status)
        self.assertEqual((20.0, 30.0), result.center_px)
        self.assertEqual(400.0, result.area_px2)
        self.assertEqual(0.0, result.orientation_deg)
        self.assertEqual((17,), result.detected_ids)
        self.assertEqual(12.5, result.detected_at_monotonic_s)

    def test_selects_target_from_multiple_markers(self) -> None:
        other = self.marker + 50.0
        vision = _FakeVision(
            frame=self.frame,
            corners=[other, self.marker],
            ids=np.array([[9], [17]], dtype=np.int32),
        )

        result = ShaftMarkerDetector(vision, ShaftMarkerConfig(marker_id=17)).detect()

        self.assertTrue(result.detected)
        self.assertEqual((9, 17), result.detected_ids)
        self.assertEqual((9, 17), tuple(marker.marker_id for marker in result.detected_markers))
        self.assertEqual((20.0, 30.0), result.center_px)

    def test_rejects_marker_below_minimum_area(self) -> None:
        vision = _FakeVision(
            frame=self.frame,
            corners=[self.marker],
            ids=np.array([[17]], dtype=np.int32),
        )

        result = ShaftMarkerDetector(
            vision,
            ShaftMarkerConfig(marker_id=17, minimum_area_px2=401.0),
        ).detect()

        self.assertEqual(MarkerDetectionStatus.MARKER_NOT_FOUND, result.status)
        self.assertEqual(400.0, result.area_px2)

    def test_reports_missing_frame(self) -> None:
        result = ShaftMarkerDetector(
            _FakeVision(frame=None),
            ShaftMarkerConfig(marker_id=17),
        ).detect()

        self.assertEqual(MarkerDetectionStatus.FRAME_UNAVAILABLE, result.status)

    def test_reports_missing_target_and_visible_ids(self) -> None:
        vision = _FakeVision(
            frame=self.frame,
            corners=[self.marker],
            ids=np.array([[9]], dtype=np.int32),
        )

        result = ShaftMarkerDetector(vision, ShaftMarkerConfig(marker_id=17)).detect()

        self.assertEqual(MarkerDetectionStatus.MARKER_NOT_FOUND, result.status)
        self.assertEqual((9,), result.detected_ids)

    def test_rejects_duplicate_target_id(self) -> None:
        vision = _FakeVision(
            frame=self.frame,
            corners=[self.marker, self.marker + 50.0],
            ids=np.array([[17], [17]], dtype=np.int32),
        )

        result = ShaftMarkerDetector(vision, ShaftMarkerConfig(marker_id=17)).detect()

        self.assertEqual(MarkerDetectionStatus.DUPLICATE_MARKER_ID, result.status)

    def test_converts_detector_exception_to_failure(self) -> None:
        vision = _FakeVision(frame=self.frame, error=RuntimeError("camera error"))

        result = ShaftMarkerDetector(vision, ShaftMarkerConfig(marker_id=17)).detect()

        self.assertEqual(MarkerDetectionStatus.DETECTION_FAILED, result.status)
        self.assertIn("camera error", result.message)

    def test_centered_region_crops_detection_and_restores_full_frame_coordinates(self) -> None:
        local_marker = np.array(
            [[[10.0, 10.0], [30.0, 10.0], [30.0, 30.0], [10.0, 30.0]]],
            dtype=np.float32,
        )
        vision = _FakeVision(
            frame=self.frame,
            corners=[local_marker],
            ids=np.array([[17]], dtype=np.int32),
        )
        detector = ShaftMarkerDetector(vision, ShaftMarkerConfig(marker_id=17))
        region = CenteredDetectionRegionProvider(width=100, height=60).resolve(120, 100)

        result = detector.detect(detection_region=region)

        self.assertEqual((60, 100, 3), vision.detected_image_shape)
        self.assertEqual(PixelRegion(x=10, y=20, width=100, height=60), result.detection_region)
        self.assertEqual((30.0, 40.0), result.center_px)

    def test_reports_clockwise_image_orientation(self) -> None:
        clockwise_marker = np.array(
            [[[20.0, 10.0], [30.0, 20.0], [20.0, 30.0], [10.0, 20.0]]],
            dtype=np.float32,
        )
        vision = _FakeVision(
            frame=self.frame,
            corners=[clockwise_marker],
            ids=np.array([[17]], dtype=np.int32),
        )

        result = ShaftMarkerDetector(vision, ShaftMarkerConfig(marker_id=17)).detect()

        self.assertAlmostEqual(45.0, result.orientation_deg)

    def test_tracker_uses_detection_to_create_next_region(self) -> None:
        vision = _FakeVision(
            frame=self.frame,
            corners=[self.marker],
            ids=np.array([[17]], dtype=np.int32),
        )
        tracker = MarkerRegionTracker(
            CenteredDetectionRegionProvider(width=100, height=100),
            padding_px=5,
            minimum_width_px=30,
            minimum_height_px=30,
            recovery_expansion_px=5,
            misses_before_fallback=2,
            detections_before_tracking=1,
            acquisition_misses_before_reset=2,
            position_filter_alpha=1.0,
            prediction_gain=1.0,
            maximum_center_jump_px=100.0,
            maximum_area_ratio_change=3.0,
        )
        detector = ShaftMarkerDetector(vision, ShaftMarkerConfig(marker_id=17))
        base_region = tracker.region_for_frame(120, 100)

        result = detector.detect(detection_region=base_region)
        tracker.record_detection(result.detected_markers[0])

        self.assertEqual(PixelRegion(10, 0, 100, 100), result.detection_region)
        self.assertEqual(PixelRegion(15, 15, 30, 30), tracker.region_for_frame(120, 100))
        self.assertEqual(TrackingState.TRACKING, tracker.state)

    def test_tracker_expands_then_falls_back_after_consecutive_misses(self) -> None:
        tracker = MarkerRegionTracker(
            CenteredDetectionRegionProvider(width=100, height=60),
            padding_px=5,
            minimum_width_px=30,
            minimum_height_px=30,
            recovery_expansion_px=5,
            misses_before_fallback=2,
            detections_before_tracking=1,
            acquisition_misses_before_reset=2,
            position_filter_alpha=1.0,
            prediction_gain=1.0,
            maximum_center_jump_px=100.0,
            maximum_area_ratio_change=3.0,
        )
        tracker.record_detection(
            DetectedMarker(
                marker_id=17,
                corners_px=((20.0, 20.0), (40.0, 20.0), (40.0, 40.0), (20.0, 40.0)),
                center_px=(30.0, 30.0),
                area_px2=400.0,
                orientation_deg=0.0,
            )
        )

        tracker.record_miss()
        self.assertEqual(TrackingState.RECOVERING, tracker.state)
        self.assertEqual(PixelRegion(10, 10, 40, 40), tracker.region_for_frame(120, 100))

        tracker.record_miss()
        self.assertEqual(TrackingState.SEARCHING, tracker.state)
        self.assertEqual(PixelRegion(10, 20, 100, 60), tracker.region_for_frame(120, 100))

    def test_tracking_region_can_follow_marker_outside_narrow_base_region(self) -> None:
        tracker = MarkerRegionTracker(
            CenteredDetectionRegionProvider(width=20, height=100),
            padding_px=5,
            minimum_width_px=30,
            minimum_height_px=30,
            recovery_expansion_px=5,
            misses_before_fallback=2,
            detections_before_tracking=1,
            acquisition_misses_before_reset=2,
            position_filter_alpha=1.0,
            prediction_gain=1.0,
            maximum_center_jump_px=100.0,
            maximum_area_ratio_change=3.0,
        )
        tracker.record_detection(
            DetectedMarker(
                marker_id=17,
                corners_px=((80.0, 40.0), (100.0, 40.0), (100.0, 60.0), (80.0, 60.0)),
                center_px=(90.0, 50.0),
                area_px2=400.0,
                orientation_deg=0.0,
            )
        )

        self.assertEqual(PixelRegion(75, 35, 30, 30), tracker.region_for_frame(120, 100))

    def test_acquisition_allows_short_gaps_between_confirming_detections(self) -> None:
        tracker = MarkerRegionTracker(
            CenteredDetectionRegionProvider(width=100, height=100),
            padding_px=5,
            minimum_width_px=30,
            minimum_height_px=30,
            recovery_expansion_px=5,
            misses_before_fallback=3,
            detections_before_tracking=3,
            acquisition_misses_before_reset=2,
            position_filter_alpha=1.0,
            prediction_gain=0.0,
            maximum_center_jump_px=100.0,
            maximum_area_ratio_change=3.0,
        )
        marker = DetectedMarker(
            marker_id=17,
            corners_px=((20.0, 20.0), (40.0, 20.0), (40.0, 40.0), (20.0, 40.0)),
            center_px=(30.0, 30.0),
            area_px2=400.0,
            orientation_deg=0.0,
        )

        tracker.record_detection(marker)
        tracker.record_miss()
        tracker.record_detection(marker)
        tracker.record_miss()
        tracker.record_detection(marker)

        self.assertEqual(TrackingState.TRACKING, tracker.state)
        self.assertEqual(PixelRegion(15, 15, 30, 30), tracker.region_for_frame(120, 100))


if __name__ == "__main__":
    unittest.main()

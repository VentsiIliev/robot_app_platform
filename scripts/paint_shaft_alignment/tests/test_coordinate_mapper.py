from __future__ import annotations

import unittest

from scripts.paint_shaft_alignment.coordinate_mapper import (
    MarkerCenterRobotMapper,
    TcpCoordinateTransformer,
)
from scripts.paint_shaft_alignment.models import (
    MarkerDetection,
    MarkerDetectionStatus,
)


class _FakeTransformer:
    def __init__(self, *, available=True, error=None):
        self.available = available
        self.error = error
        self.received = None

    def is_available(self):
        return self.available

    def transform(self, x, y):
        self.received = (x, y)
        if self.error is not None:
            raise self.error
        return x / 2.0, -y / 4.0


class _FakeTcpTransformer:
    def __init__(self):
        self.received = None

    def is_available(self):
        return True

    def transform_to_tcp(self, x, y):
        self.received = (x, y)
        return x + 10.0, y - 20.0


class MarkerCenterRobotMapperTests(unittest.TestCase):
    def test_tcp_adapter_uses_camera_to_tcp_conversion(self):
        transformer = _FakeTcpTransformer()
        mapper = MarkerCenterRobotMapper(TcpCoordinateTransformer(transformer))

        result = mapper.map_center((12.0, 34.0))

        self.assertTrue(result.available)
        self.assertEqual((12.0, 34.0), transformer.received)
        self.assertEqual((22.0, 14.0), (result.x_mm, result.y_mm))

    def test_maps_detected_center_through_paint_transformer(self):
        transformer = _FakeTransformer()
        detection = MarkerDetection(
            status=MarkerDetectionStatus.DETECTED,
            detected_at_monotonic_s=1.0,
            marker_id=2,
            center_px=(640.0, 360.0),
        )

        result = MarkerCenterRobotMapper(transformer).map(detection)

        self.assertTrue(result.available)
        self.assertEqual((640.0, 360.0), transformer.received)
        self.assertEqual((320.0, -90.0), (result.x_mm, result.y_mm))

    def test_does_not_map_when_marker_is_missing(self):
        transformer = _FakeTransformer()
        detection = MarkerDetection(
            status=MarkerDetectionStatus.MARKER_NOT_FOUND,
            detected_at_monotonic_s=1.0,
            marker_id=2,
        )

        result = MarkerCenterRobotMapper(transformer).map(detection)

        self.assertFalse(result.available)
        self.assertIsNone(transformer.received)

    def test_reports_unavailable_calibration(self):
        detection = MarkerDetection(
            status=MarkerDetectionStatus.DETECTED,
            detected_at_monotonic_s=1.0,
            marker_id=2,
            center_px=(640.0, 360.0),
        )

        result = MarkerCenterRobotMapper(_FakeTransformer(available=False)).map(detection)

        self.assertFalse(result.available)
        self.assertIn("calibration", result.message.lower())


if __name__ == "__main__":
    unittest.main()

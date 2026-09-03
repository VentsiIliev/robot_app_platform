from __future__ import annotations

import unittest

from scripts.paint_shaft_alignment.models import DetectedMarker
from scripts.paint_shaft_alignment.stabilizer import MarkerSampleStabilizer


def _marker(x: float, y: float, orientation: float) -> DetectedMarker:
    return DetectedMarker(
        marker_id=2,
        corners_px=((x - 1, y - 1), (x + 1, y - 1), (x + 1, y + 1), (x - 1, y + 1)),
        center_px=(x, y),
        area_px2=4.0,
        orientation_deg=orientation,
    )


class MarkerSampleStabilizerTests(unittest.TestCase):
    def test_requires_window_and_reports_median_center(self):
        stabilizer = MarkerSampleStabilizer(
            required_samples=3,
            maximum_center_spread_px=2.0,
            maximum_orientation_spread_deg=2.0,
            misses_before_reset=2,
        )

        stabilizer.record_detection(_marker(10.0, 20.0, 5.0))
        stabilizer.record_detection(_marker(11.0, 19.0, 6.0))
        result = stabilizer.record_detection(_marker(10.5, 20.5, 5.5))

        self.assertTrue(result.stable)
        self.assertEqual((10.5, 20.0), result.center_px)

    def test_rejects_large_position_spread(self):
        stabilizer = MarkerSampleStabilizer(
            required_samples=3,
            maximum_center_spread_px=2.0,
            maximum_orientation_spread_deg=5.0,
            misses_before_reset=2,
        )

        stabilizer.record_detection(_marker(10.0, 20.0, 0.0))
        stabilizer.record_detection(_marker(10.5, 20.0, 0.0))
        result = stabilizer.record_detection(_marker(30.0, 20.0, 0.0))

        self.assertFalse(result.stable)
        self.assertGreater(result.center_spread_px, 2.0)

    def test_circular_orientation_mean_handles_wrap(self):
        stabilizer = MarkerSampleStabilizer(
            required_samples=2,
            maximum_center_spread_px=1.0,
            maximum_orientation_spread_deg=3.0,
            misses_before_reset=2,
        )

        stabilizer.record_detection(_marker(10.0, 20.0, 179.0))
        result = stabilizer.record_detection(_marker(10.0, 20.0, -179.0))

        self.assertTrue(result.stable)
        self.assertAlmostEqual(-180.0, result.orientation_deg)
        self.assertAlmostEqual(1.0, result.orientation_spread_deg)

    def test_consecutive_misses_clear_samples(self):
        stabilizer = MarkerSampleStabilizer(
            required_samples=2,
            maximum_center_spread_px=1.0,
            maximum_orientation_spread_deg=1.0,
            misses_before_reset=2,
        )
        stabilizer.record_detection(_marker(10.0, 20.0, 0.0))

        stabilizer.record_miss()
        result = stabilizer.record_miss()

        self.assertEqual(0, result.sample_count)
        self.assertFalse(result.stable)


if __name__ == "__main__":
    unittest.main()

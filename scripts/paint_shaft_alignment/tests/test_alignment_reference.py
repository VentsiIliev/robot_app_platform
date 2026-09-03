from __future__ import annotations

import unittest

from scripts.paint_shaft_alignment.alignment_reference import (
    AlignmentMisalignment,
    AlignmentReference,
    AlignmentReferenceCapture,
    MisalignmentThresholds,
)


class AlignmentReferenceCaptureTests(unittest.TestCase):
    def test_restores_a_persisted_reference_without_capturing(self):
        capture = AlignmentReferenceCapture(30)
        reference = AlignmentReference(1.0, 2.0, 3.0, 11.0, 10.9)

        capture.restore(reference)

        self.assertEqual(reference, capture.reference)
        self.assertFalse(capture.capturing)
        self.assertEqual(0, capture.sample_count)

    def test_thresholds_report_each_exceeded_absolute_limit(self):
        thresholds = MisalignmentThresholds(1.0, 2.0, 3.0, 0.5, 0.6)
        value = AlignmentMisalignment(
            True,
            dx_mm=-1.1,
            dy_mm=2.0,
            orientation_difference_deg=3.1,
            marker_width_difference_mm=-0.7,
            marker_height_difference_mm=0.6,
        )

        self.assertEqual(("dX", "dRZ", "dW"), thresholds.exceeded_by(value))

    def test_collects_required_samples_and_reports_signed_misalignment(self):
        capture = AlignmentReferenceCapture(required_samples=3)
        capture.start()

        self.assertFalse(capture.record(9.0, 21.0, 179.0, 10.8, 11.2))
        self.assertFalse(capture.record(10.0, 20.0, -179.0, 11.0, 11.0))
        self.assertTrue(capture.record(11.0, 19.0, 180.0, 11.2, 10.8))

        self.assertFalse(capture.capturing)
        self.assertEqual((10.0, 20.0), (capture.reference.x_mm, capture.reference.y_mm))
        self.assertEqual(
            (11.0, 11.0),
            (capture.reference.marker_width_mm, capture.reference.marker_height_mm),
        )
        result = capture.compare(12.5, 18.0, -178.0, 12.0, 10.5)
        self.assertTrue(result.available)
        self.assertEqual((2.5, -2.0), (result.dx_mm, result.dy_mm))
        self.assertAlmostEqual(2.0, result.orientation_difference_deg)
        self.assertEqual(
            (1.0, -0.5),
            (result.marker_width_difference_mm, result.marker_height_difference_mm),
        )

    def test_start_replaces_previous_reference(self):
        capture = AlignmentReferenceCapture(required_samples=1)
        capture.start()
        capture.record(1.0, 2.0, 3.0, 11.0, 11.0)

        capture.start()

        self.assertTrue(capture.capturing)
        self.assertIsNone(capture.reference)
        self.assertEqual(0, capture.sample_count)

    def test_start_can_change_sample_count_for_next_capture(self):
        capture = AlignmentReferenceCapture(required_samples=30)

        capture.start(required_samples=2)

        self.assertEqual(2, capture.required_samples)
        self.assertFalse(capture.record(1.0, 2.0, 3.0, 11.0, 11.0))
        self.assertTrue(capture.record(1.0, 2.0, 3.0, 11.0, 11.0))


if __name__ == "__main__":
    unittest.main()

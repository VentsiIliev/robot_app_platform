import unittest
import time

from src.applications.shaft_alignment.model.shaft_alignment_model import ShaftAlignmentModel
from src.applications.shaft_alignment.service.i_shaft_alignment_service import AlignmentThresholds
from src.applications.shaft_alignment.service.stub_shaft_alignment_service import StubShaftAlignmentService


class ShaftAlignmentModelTests(unittest.TestCase):
    def test_check_alignment_fails_safe_without_reference_and_returns_boolean(self):
        service = StubShaftAlignmentService()
        model = ShaftAlignmentModel(service)
        model.start()
        self.assertFalse(model.check_alignment())
        model.capture_reference(1)
        time.sleep(0.11)
        self.assertIsInstance(model.check_alignment(), bool)
        model.close()

    def test_delegates_lifecycle_reference_and_thresholds(self):
        service = StubShaftAlignmentService()
        model = ShaftAlignmentModel(service)
        model.start()
        model.set_thresholds(AlignmentThresholds(1.0, 1.0, 1.0, 0.5, 0.5))
        model.capture_reference(2)

        snapshot = model.refresh()

        self.assertTrue(snapshot.running)
        self.assertTrue(snapshot.reference_capturing)
        self.assertEqual(1.0, service.get_settings().misalignment_dx_threshold_mm)
        model.close()
        self.assertFalse(model.refresh().running)

    def test_completed_reference_updates_in_memory_settings(self):
        service = StubShaftAlignmentService()
        model = ShaftAlignmentModel(service)
        model.start()
        model.capture_reference(1)
        time.sleep(0.11)

        snapshot = model.refresh()

        self.assertTrue(snapshot.reference_available)
        self.assertEqual(257.75, service.get_settings().reference_tcp_x_mm)
        self.assertEqual(11.0, service.get_settings().reference_marker_width_mm)
        self.assertEqual(
            4, len(service.get_settings().reference_marker_corners_normalized)
        )
        self.assertEqual(
            (0.56, 0.70),
            service.get_settings().reference_point_of_interest_normalized,
        )


if __name__ == "__main__":
    unittest.main()

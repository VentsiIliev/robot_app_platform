import unittest
import json
import tempfile
import threading
from collections import deque
from pathlib import Path

from src.applications.shaft_alignment.settings import (
    ShaftAlignmentSettings,
    ShaftAlignmentSettingsSerializer,
)
from src.applications.shaft_alignment.service.paint_vision_shaft_alignment_service import (
    PaintVisionShaftAlignmentService,
)
from src.applications.shaft_alignment.service.i_shaft_alignment_service import (
    AlignmentSnapshot,
    AlignmentThresholds,
)


class ShaftAlignmentSettingsTests(unittest.TestCase):
    def test_round_trip_preserves_all_settings(self):
        serializer = ShaftAlignmentSettingsSerializer()
        settings = ShaftAlignmentSettings(
            marker_id=7,
            marker_size_mm=12.5,
            reference_tcp_x_mm=257.75,
            reference_tcp_y_mm=215.7,
            reference_orientation_deg=0.4,
            reference_marker_width_mm=11.1,
            reference_marker_height_mm=10.9,
            reference_marker_corners_normalized=(
                (0.1, 0.2), (0.3, 0.2), (0.3, 0.4), (0.1, 0.4),
            ),
            reference_point_of_interest_normalized=(0.34, 0.62),
        )

        restored = serializer.from_dict(serializer.to_dict(settings))

        self.assertEqual(settings, restored)
        self.assertEqual("shaft_alignment", serializer.settings_type)

    def test_runtime_state_updates_memory_and_json_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            service = PaintVisionShaftAlignmentService.__new__(
                PaintVisionShaftAlignmentService
            )
            service._lock = threading.RLock()
            service._settings_path = Path(directory) / "config.json"
            service._stored_settings = ShaftAlignmentSettings()
            service._config = ShaftAlignmentSettings()

            with service._lock:
                service._persist_runtime_state(
                    reference_tcp_x_mm=257.75,
                    reference_tcp_y_mm=215.7,
                    reference_orientation_deg=0.4,
                    reference_marker_width_mm=11.1,
                    reference_marker_height_mm=10.9,
                    reference_marker_corners_normalized=(
                        (0.1, 0.2), (0.3, 0.2),
                        (0.3, 0.4), (0.1, 0.4),
                    ),
                    reference_point_of_interest_normalized=(0.34, 0.62),
                )

            payload = json.loads(service._settings_path.read_text(encoding="utf-8"))
            self.assertEqual(257.75, service._stored_settings.reference_tcp_x_mm)
            self.assertEqual(10.9, service._config.reference_marker_height_mm)
            self.assertEqual(
                [0.1, 0.2], payload["reference_marker_corners_normalized"][0]
            )
            self.assertEqual(
                [0.34, 0.62], payload["reference_point_of_interest_normalized"]
            )

            service.set_thresholds(AlignmentThresholds(1.2, 1.3, 1.4, 0.6, 0.7))

            payload = json.loads(service._settings_path.read_text(encoding="utf-8"))
            self.assertEqual(1.2, payload["misalignment_dx_threshold_mm"])
            self.assertEqual(1.4, service._stored_settings.misalignment_drz_threshold_deg)
            self.assertEqual(0.7, service._config.misalignment_dh_threshold_mm)

    def test_point_of_interest_uses_aligned_marker_image_axes(self):
        service = PaintVisionShaftAlignmentService.__new__(
            PaintVisionShaftAlignmentService
        )
        service._config = ShaftAlignmentSettings(
            marker_size_mm=10.0,
            point_of_interest_x_offset_mm=2.0,
            point_of_interest_y_offset_mm=5.0,
        )

        point = service._point_of_interest_for_corners(
            ((40.0, 40.0), (60.0, 40.0), (60.0, 60.0), (40.0, 60.0)),
            100,
            100,
        )

        self.assertAlmostEqual(0.54, point[0])
        self.assertAlmostEqual(0.60, point[1])

    def test_alignment_check_uses_configured_median_sample_batch(self):
        service = PaintVisionShaftAlignmentService.__new__(
            PaintVisionShaftAlignmentService
        )
        service._lock = threading.RLock()
        service._config = ShaftAlignmentSettings(alignment_check_samples=3)
        service._thresholds = AlignmentThresholds(1.0, 1.0, 1.0, 0.5, 0.5)
        service._snapshot = AlignmentSnapshot(
            running=True,
            detected=True,
            reference_available=True,
        )
        service._check_samples = deque(
            ((0.1, 0.1, 0.1, 0.1, 0.1), (4.0, 4.0, 4.0, 4.0, 4.0)),
            maxlen=3,
        )
        self.assertFalse(service.check_alignment())

        service._check_samples.append((0.2, 0.2, 0.2, 0.2, 0.2))
        self.assertTrue(service.check_alignment())

        service._check_samples.clear()
        service._check_samples.extend(
            ((2.0, 2.0, 2.0, 1.0, 1.0),) * 2
            + ((0.1, 0.1, 0.1, 0.1, 0.1),)
        )
        self.assertFalse(service.check_alignment())


if __name__ == "__main__":
    unittest.main()

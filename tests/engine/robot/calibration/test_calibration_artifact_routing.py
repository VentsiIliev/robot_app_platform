import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.calibration.service_builders import _CalibrationArtifactVisionProxy
from src.engine.vision.calibration_vision_settings import CoordinateCalibrationProfile


class TestCalibrationArtifactRouting(unittest.TestCase):
    def test_destination_is_frozen_for_the_calibration_session(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            global_path = str(Path(temp_dir) / "camera.npy")
            vision = MagicMock()
            vision.camera_to_robot_matrix_path = global_path
            settings_service = MagicMock()
            settings = SimpleNamespace(
                calibration_target_work_area="magazine",
                work_area_calibration_profiles={"magazine": "magazine_local"},
                coordinate_calibration_profiles={
                    "magazine_local": CoordinateCalibrationProfile(
                        matrix_path="calibrations/magazine/camera.npy",
                        reference_frame="magazine",
                    )
                },
            )
            settings_service.get.return_value = settings
            proxy = _CalibrationArtifactVisionProxy(vision, settings_service)

            proxy.begin_calibration()
            locked_path = proxy.camera_to_robot_matrix_path
            settings.calibration_target_work_area = "global"

            self.assertEqual(proxy.get_calibration_target_area_id(), "magazine")
            self.assertEqual(proxy.camera_to_robot_matrix_path, locked_path)
            proxy.end_calibration()
            self.assertEqual(proxy.get_calibration_target_area_id(), "global")
            self.assertEqual(proxy.camera_to_robot_matrix_path, global_path)

    def test_shared_global_profile_cannot_be_overwritten_as_an_area_target(self):
        vision = MagicMock()
        vision.camera_to_robot_matrix_path = "/tmp/global.npy"
        settings_service = MagicMock()
        settings_service.get.return_value = SimpleNamespace(
            calibration_target_work_area="magazine",
            work_area_calibration_profiles={"magazine": "global"},
            coordinate_calibration_profiles={},
        )
        proxy = _CalibrationArtifactVisionProxy(vision, settings_service)

        with self.assertRaisesRegex(RuntimeError, "dedicated profile"):
            proxy.begin_calibration()


if __name__ == "__main__":
    unittest.main()

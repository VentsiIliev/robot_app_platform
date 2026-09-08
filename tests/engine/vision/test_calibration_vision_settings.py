import unittest

from src.engine.vision.calibration_vision_settings import (
    CalibrationVisionSettings,
    CoordinateCalibrationProfile,
)


class TestCalibrationVisionSettings(unittest.TestCase):
    def test_legacy_data_defaults_to_global_mode(self):
        settings = CalibrationVisionSettings.from_dict({"Calibration": {}})
        self.assertEqual(settings.coordinate_calibration_mode, "global")
        self.assertEqual(settings.coordinate_calibration_profiles, {})
        self.assertEqual(settings.work_area_calibration_profiles, {})

    def test_profiles_and_explicit_area_assignments_round_trip(self):
        original = CalibrationVisionSettings(
            coordinate_calibration_mode="per_area",
            coordinate_calibration_profiles={
                "magazine_local": CoordinateCalibrationProfile(
                    matrix_path="calibrations/magazine/camera_to_robot.npy",
                    reference_frame="magazine",
                )
            },
            work_area_calibration_profiles={
                "paint": "global",
                "magazine": "magazine_local",
                "vertical_shaft_alignment": "global",
            },
        )
        restored = CalibrationVisionSettings.from_dict(original.to_dict())
        self.assertEqual(restored, original)

    def test_invalid_mode_falls_back_to_global(self):
        settings = CalibrationVisionSettings.from_dict(
            {"Coordinate calibration": {"Mode": "unexpected"}}
        )
        self.assertEqual(settings.coordinate_calibration_mode, "global")


if __name__ == "__main__":
    unittest.main()

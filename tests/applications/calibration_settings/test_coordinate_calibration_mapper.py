import unittest
from unittest.mock import MagicMock

from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.calibration_settings.mapper import CalibrationSettingsMapper
from src.engine.vision.calibration_vision_settings import (
    CalibrationVisionSettings,
    CoordinateCalibrationProfile,
)


class TestCoordinateCalibrationMapper(unittest.TestCase):
    def _data(self):
        return CalibrationSettingsData(
            vision=CalibrationVisionSettings(),
            robot=MagicMock(),
            height=MagicMock(),
        )

    def test_ui_fields_round_trip_profiles_and_assignments(self):
        data = self._data()
        flat = CalibrationSettingsMapper.to_flat_dict(data)
        flat.update(
            {
                "coordinate_calibration_mode": "per_area",
                "coordinate_calibration_profiles": (
                    '{"magazine_local":{"matrix_path":"magazine.npy",'
                    '"reference_frame":"magazine"}}'
                ),
                "work_area_calibration_profiles": (
                    '{"paint":"global","magazine":"magazine_local"}'
                ),
            }
        )

        updated = CalibrationSettingsMapper.from_flat_dict(flat, data)

        self.assertEqual(updated.vision.coordinate_calibration_mode, "per_area")
        self.assertEqual(
            updated.vision.coordinate_calibration_profiles["magazine_local"],
            CoordinateCalibrationProfile("magazine.npy", "magazine"),
        )
        self.assertEqual(
            updated.vision.work_area_calibration_profiles,
            {"paint": "global", "magazine": "magazine_local"},
        )

    def test_invalid_profile_json_is_rejected(self):
        data = self._data()
        flat = CalibrationSettingsMapper.to_flat_dict(data)
        flat["coordinate_calibration_profiles"] = "not json"
        with self.assertRaisesRegex(ValueError, "must be valid JSON"):
            CalibrationSettingsMapper.from_flat_dict(flat, data)


if __name__ == "__main__":
    unittest.main()

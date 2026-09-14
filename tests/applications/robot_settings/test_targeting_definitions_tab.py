import sys
import unittest

from PyQt6.QtWidgets import QApplication

from src.applications.robot_settings.view.targeting_definitions_tab import (
    TargetingDefinitionsTab,
    _apply_calibration_choice,
    _calibration_choice,
)


class TestTargetingDefinitionsTab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_calibration_profile_fields_round_trip_with_frame(self):
        tab = TargetingDefinitionsTab()
        payload = {
            "coordinate_calibration_mode": "per_area",
            "frames": [
                {
                    "name": "magazine",
                    "work_area_id": "magazine",
                    "source_navigation_group": "CALIBRATION",
                    "target_navigation_group": "Magazine",
                    "use_height_correction": True,
                    "calibration_profile": "magazine_local",
                    "calibration_reference_frame": "magazine",
                    "calibration_matrix_path": "calibrations/magazine/camera_to_robot.npy",
                }
            ],
        }

        tab.load(payload)
        saved = tab.get_values()

        self.assertEqual(saved["coordinate_calibration_mode"], "per_area")
        self.assertEqual(saved["frames"][0]["calibration_profile"], "magazine_local")
        self.assertEqual(saved["frames"][0]["calibration_reference_frame"], "magazine")
        self.assertEqual(
            saved["frames"][0]["calibration_matrix_path"],
            "calibrations/magazine/camera_to_robot.npy",
        )

    def test_loading_mode_does_not_emit_user_change(self):
        tab = TargetingDefinitionsTab()
        emissions = []
        tab.definitions_changed.connect(lambda: emissions.append(True))

        tab.load({"coordinate_calibration_mode": "per_area"})

        self.assertEqual(emissions, [])

    def test_local_choice_derives_internal_profile_values(self):
        frame = _apply_calibration_choice(
            {"name": "magazine", "work_area_id": "magazine"},
            "local",
        )

        self.assertEqual(frame["calibration_profile"], "magazine_local")
        self.assertEqual(frame["calibration_reference_frame"], "magazine")
        self.assertEqual(
            frame["calibration_matrix_path"],
            "calibrations/magazine/camera_to_robot.npy",
        )
        self.assertEqual(_calibration_choice(frame), "local")

    def test_global_and_not_configured_choices_clear_internal_local_values(self):
        local = _apply_calibration_choice(
            {"work_area_id": "paint"},
            "local",
        )

        global_frame = _apply_calibration_choice(local, "global")
        empty_frame = _apply_calibration_choice(local, "none")

        self.assertEqual(_calibration_choice(global_frame), "global")
        self.assertEqual(global_frame["calibration_matrix_path"], "")
        self.assertEqual(_calibration_choice(empty_frame), "none")
        self.assertEqual(empty_frame["calibration_profile"], "")


if __name__ == "__main__":
    unittest.main()

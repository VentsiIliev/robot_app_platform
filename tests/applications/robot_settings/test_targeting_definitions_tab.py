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

    def test_per_area_points_and_tcp_can_reuse_global_independently(self):
        tab = TargetingDefinitionsTab()
        tab.load({
            "points": [{"name": "tool", "display_name": "Tool", "x_mm": 1, "y_mm": 2}],
            "frames": [{"name": "magazine", "work_area_id": "magazine"}],
            "camera_to_tcp_global": {"x_mm": 3, "y_mm": 4, "rotation_residuals": []},
        })
        tab._per_area_points.setChecked(True)
        tab._point_area.setCurrentIndex(tab._point_area.findData("magazine"))
        tab._local_points.setChecked(True)
        tab._points[0]["x_mm"] = 9
        tab._per_area_tcp.setChecked(True)
        emissions = []
        tab.definitions_changed.connect(lambda: emissions.append(True))
        tab._tcp_area.setCurrentIndex(tab._tcp_area.findData("magazine"))
        self.assertEqual(emissions, [])
        tab._local_tcp.setChecked(True)
        tab._tcp_x.setValue(12)

        saved = tab.get_values()
        self.assertEqual(saved["points"][0]["x_mm"], 1)
        self.assertEqual(saved["area_points"]["magazine"][0]["x_mm"], 9)
        self.assertEqual(saved["camera_to_tcp_global"]["x_mm"], 3)
        self.assertEqual(saved["camera_to_tcp_by_area"]["magazine"]["x_mm"], 12)
        tab._local_points.setChecked(False)
        self.assertNotIn("magazine", tab.get_values()["area_points"])
        self.assertIn("magazine", tab.get_values()["camera_to_tcp_by_area"])

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

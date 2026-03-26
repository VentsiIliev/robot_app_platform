import sys
import unittest

from PyQt6.QtWidgets import QApplication, QWidget

from src.applications.calibration.view.calibration_controls_panel import CalibrationControlsPanel


class TestCalibrationControlsPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_uses_phase_tabs_for_workflow_sections(self):
        panel = CalibrationControlsPanel()
        tab_titles = [panel._tabs.tabText(i) for i in range(panel._tabs.count())]
        self.assertEqual(
            tab_titles,
            ["System", "Camera", "Robot", "Laser", "Height Mapping"],
        )

    def test_stop_button_starts_disabled(self):
        panel = CalibrationControlsPanel()
        self.assertFalse(panel.stop_robot_btn.isEnabled())

    def test_each_phase_tab_exposes_save_settings_button(self):
        panel = CalibrationControlsPanel()
        self.assertEqual(len(panel.iter_save_settings_buttons()), 4)

    def test_height_mapping_content_can_be_injected_after_init(self):
        panel = CalibrationControlsPanel()
        widget = QWidget()

        panel.set_height_mapping_content(widget)

        self.assertIs(panel._height_tab._height_mapping_content, widget)
        self.assertIs(widget.parentWidget(), panel._height_tab._card)

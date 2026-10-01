import sys
import unittest

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QComboBox, QWidget

from src.applications.calibration.view.calibration_controls_panel import CalibrationControlsPanel
from src.applications.calibration.view.calibration_view import CalibrationView
from src.applications.calibration.calibration_factory import CalibrationFactory
from src.applications.calibration.view.compact_settings_group import CompactSettingsGroup
from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField
from src.applications.calibration_settings.view.calibration_settings_schema import CALIBRATION_MARKER_GROUP
from src.applications.intrinsic_calibration_capture.service.i_intrinsic_capture_service import IntrinsicCaptureConfig
from src.shared_contracts.declarations import WorkAreaDefinition


class TestCalibrationControlsPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_uses_phase_tabs_for_workflow_sections(self):
        panel = CalibrationControlsPanel()
        tab_titles = [panel.phase_bar.tabText(i) for i in range(panel.phase_bar.count())]
        self.assertEqual(
            tab_titles,
            ["System", "Camera", "Robot", "Tool TCP", "WorkObject", "Laser", "Height Mapping"],
        )
        panel.phase_bar.setCurrentIndex(6)
        self.assertEqual(panel._tabs.currentIndex(), 6)

    def test_factory_can_hide_optional_phases(self):
        view = CalibrationFactory(
            show_laser_tab=False,
            show_height_mapping_tab=False,
        )._create_view()
        panel = view._controls_panel
        tab_titles = [panel.phase_bar.tabText(i) for i in range(panel.phase_bar.count())]
        self.assertEqual(tab_titles, ["System", "Camera", "Robot", "Tool TCP", "WorkObject"])
        self.assertEqual(len(panel.iter_save_settings_buttons()), 2)
        panel.phase_bar.setCurrentIndex(4)
        self.assertEqual(panel._tabs.currentIndex(), 4)

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

    def test_cancel_settings_dialog_restores_values(self):
        panel = CalibrationControlsPanel()
        camera_tab = panel._phase_pages[1]
        key = "calib_vision_chessboard_width"
        original = camera_tab.get_settings_values()[key]
        original_cols = panel.intrinsic_auto_capture.get_config().chessboard_width
        original_board_type = panel.intrinsic_auto_capture.get_config().board_type
        saved = []
        camera_tab.auto_capture_config_saved.connect(saved.append)

        def cancel_after_edit():
            camera_tab.set_settings_values({key: original + 1})
            panel.intrinsic_auto_capture._board_cols.setValue(original_cols + 1)
            panel.intrinsic_auto_capture._rb_chessboard.setChecked(True)
            camera_tab._settings_dialog.reject()

        QTimer.singleShot(0, cancel_after_edit)
        camera_tab._settings_open_button.click()
        self.assertEqual(camera_tab.get_settings_values()[key], original)
        self.assertEqual(panel.intrinsic_auto_capture.get_config().chessboard_width, original_cols)
        self.assertEqual(panel.intrinsic_auto_capture.get_config().board_type, original_board_type)
        self.assertEqual(saved, [])

    def test_camera_auto_capture_fields_share_settings_dialog(self):
        panel = CalibrationControlsPanel()
        camera_tab = panel.camera_tab

        self.assertEqual(camera_tab._settings_tabs.count(), 2)
        self.assertIs(
            camera_tab._settings_tabs.widget(1).widget(),
            panel.intrinsic_auto_capture.settings_widget(),
        )
        self.assertEqual(panel.intrinsic_auto_capture.findChildren(KeyboardNumberField), [])

    def test_camera_settings_save_emits_auto_capture_config(self):
        panel = CalibrationControlsPanel()
        camera_tab = panel.camera_tab
        panel.intrinsic_auto_capture.set_config(
            IntrinsicCaptureConfig(margin_px=84.0, max_detection_retries=7)
        )
        saved = []
        camera_tab.auto_capture_config_saved.connect(saved.append)

        def save_after_edit():
            panel.intrinsic_auto_capture._board_cols.setValue(12)
            camera_tab._save_button.click()

        QTimer.singleShot(0, save_after_edit)
        camera_tab._settings_open_button.click()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].chessboard_width, 12)
        self.assertEqual(saved[0].margin_px, 84.0)
        self.assertEqual(saved[0].max_detection_retries, 7)

    def test_compact_settings_keep_schema_value_types(self):
        group = CompactSettingsGroup(CALIBRATION_MARKER_GROUP)
        group.set_values({
            "calib_run_height_measurement": "False",
            "calib_z_target": 150,
            "calib_required_ids": [1, 4, 8],
        })
        values = group.get_values()
        self.assertEqual(values["calib_run_height_measurement"], "False")
        self.assertEqual(values["calib_z_target"], 150)
        self.assertEqual(values["calib_required_ids"], [1, 4, 8])

    def test_workobject_steps_preserve_capture_and_solve_flow(self):
        panel = CalibrationControlsPanel()
        tab = panel.workobject_tab
        captured = []
        tab.capture_requested.connect(captured.append)
        for _name, _value, button, _source, key in tab._step_widgets:
            button.click()
            tab.set_capture_result(key, [1, 2, 3, 0, 0, 0])
            tab.set_result(True, "Captured", {"point": key})
        self.assertEqual(captured, ["center", "x", "y"])
        self.assertTrue(tab._solve_btn.isEnabled())
        self.assertFalse(tab._save_btn.isEnabled())
        tab.set_result(True, "Solved", {"transform": [0, 0, 0, 0, 0, 0]})
        self.assertTrue(tab._save_btn.isEnabled())

    def test_area_picker_returns_selected_area_id(self):
        definition = WorkAreaDefinition(id="paint", label="Paint", color="#FF8800", supports_height_mapping=True)
        view = CalibrationView([definition])

        def choose_paint():
            dialog = QApplication.activeModalWidget()
            combo = dialog.findChild(QComboBox)
            combo.setCurrentIndex(1)
            dialog.accept()

        QTimer.singleShot(0, choose_paint)
        self.assertEqual(view.prompt_camera_tcp_calibration_area(), "paint")

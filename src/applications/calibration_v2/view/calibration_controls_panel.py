from __future__ import annotations

from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from src.applications.calibration_settings.view.calibration_settings_schema import (
    CALIBRATION_ADAPTIVE_GROUP,
    CALIBRATION_AXIS_MAPPING_GROUP,
    CALIBRATION_CAMERA_TCP_GROUP,
    CALIBRATION_MARKER_GROUP,
    HEIGHT_MAPPING_GROUP,
    LASER_CALIBRATION_GROUP,
    LASER_DETECTION_GROUP,
    VISION_CALIBRATION_GROUP,
)
from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from src.applications.base.app_styles import (
    APP_DANGER_BUTTON_STYLE,
    APP_PANEL_BG,
    APP_PRIMARY_BUTTON_STYLE,
    APP_SECONDARY_BUTTON_STYLE,
    APP_SEQUENCE_BUTTON_STYLE,
    APP_TOGGLE_OFF_BUTTON_STYLE,
    APP_TOGGLE_ON_BUTTON_STYLE,
)
from src.applications.calibration.view.calibration_phase_tabs import (
    CameraCalibrationTab,
    HeightMappingTab,
    LaserCalibrationTab,
    RobotCalibrationTab,
    SystemCalibrationTab,
)


class CalibrationControlsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._crosshair_on = False
        self._magnifier_on = False
        self._height_mapping_content: QWidget | None = None
        self._phase_tabs: list[QWidget] = []
        self._build_ui()

    def _build_ui(self) -> None:
        # Tab widget fills the panel; the tab bar is always visible at the top.
        # Each individual tab wraps its own content in a QScrollArea so tall
        # settings sections don't push the tab bar off-screen.
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ background: {APP_PANEL_BG}; border-left: 1px solid #E0E0E0; }}"
            f"QTabBar::tab {{ min-height: 40px; min-width: 64px; padding: 0 10px;"
            f"  font-size: 9pt; font-weight: bold; }}"
            f"QTabBar::tab:selected {{ border-bottom: 3px solid #905BA9; }}"
        )

        self.capture_btn = MaterialButton("Capture Calibration Image")
        self.capture_btn.setStyleSheet(APP_SECONDARY_BUTTON_STYLE)
        self.crosshair_btn = MaterialButton("⊕  Crosshair")
        self.crosshair_btn.setStyleSheet(APP_TOGGLE_OFF_BUTTON_STYLE)
        self.magnifier_btn = MaterialButton("🔍  Magnifier")
        self.magnifier_btn.setStyleSheet(APP_TOGGLE_OFF_BUTTON_STYLE)
        self.calibrate_camera_btn = MaterialButton("Calibrate Camera")
        self.calibrate_camera_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        self.calibrate_robot_btn = MaterialButton("Calibrate Robot")
        self.calibrate_robot_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        self.calibrate_camera_tcp_offset_btn = MaterialButton("Calibrate Camera TCP Offset")
        self.calibrate_camera_tcp_offset_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        self.calibrate_camera_tcp_offset_btn.setEnabled(False)
        self.calibrate_sequence_btn = MaterialButton("Calibrate Camera → Robot")
        self.calibrate_sequence_btn.setStyleSheet(APP_SEQUENCE_BUTTON_STYLE)
        self.stop_robot_btn = MaterialButton("⏹  Stop Active Task")
        self.stop_robot_btn.setStyleSheet(APP_DANGER_BUTTON_STYLE)
        self.stop_robot_btn.setEnabled(False)
        self.test_calibration_btn = MaterialButton("▶  Test Calibration")
        self.test_calibration_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        self.test_calibration_btn.setEnabled(False)
        self.calibrate_laser_btn = MaterialButton("📡  Calibrate Laser")
        self.calibrate_laser_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        self.detect_laser_btn = MaterialButton("🔎  Detect Laser Once")
        self.detect_laser_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        self.measure_marker_heights_btn = MaterialButton("📏  Measure Marker Heights")
        self.measure_marker_heights_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        self.measure_marker_heights_btn.setEnabled(False)
        self.measure_marker_heights_btn.hide()
        self.verify_saved_model_btn = MaterialButton("🧪  Verify Saved Model")
        self.verify_saved_model_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        self.verify_saved_model_btn.setEnabled(False)

        self._tabs.addTab(self._build_system_tab(), "System")
        self._tabs.addTab(self._build_camera_tab(), "Camera")
        self._tabs.addTab(self._build_robot_tab(), "Robot")
        self._tabs.addTab(self._build_laser_tab(), "Laser")
        self._tabs.addTab(self._build_height_tab(), "Height")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._tabs)  # tab bar always pinned at top, no outer scroll

    def _build_camera_tab(self) -> QWidget:
        tab = CameraCalibrationTab(
            capture_btn=self.capture_btn,
            crosshair_btn=self.crosshair_btn,
            magnifier_btn=self.magnifier_btn,
            calibrate_camera_btn=self.calibrate_camera_btn,
            settings_schemas=[VISION_CALIBRATION_GROUP],
        )
        self._phase_tabs.append(tab)
        return tab

    def _build_robot_tab(self) -> QWidget:
        tab = RobotCalibrationTab(
            calibrate_robot_btn=self.calibrate_robot_btn,
            calibrate_tcp_btn=self.calibrate_camera_tcp_offset_btn,
            test_btn=self.test_calibration_btn,
            settings_schemas=[
                CALIBRATION_ADAPTIVE_GROUP,
                CALIBRATION_MARKER_GROUP,
                CALIBRATION_AXIS_MAPPING_GROUP,
                CALIBRATION_CAMERA_TCP_GROUP,
            ],
        )
        self._phase_tabs.append(tab)
        return tab

    def _build_laser_tab(self) -> QWidget:
        tab = LaserCalibrationTab(
            calibrate_laser_btn=self.calibrate_laser_btn,
            detect_laser_btn=self.detect_laser_btn,
            settings_schemas=[LASER_DETECTION_GROUP, LASER_CALIBRATION_GROUP],
        )
        self._phase_tabs.append(tab)
        return tab

    def _build_height_tab(self) -> QWidget:
        tab = HeightMappingTab(
            verify_saved_model_btn=self.verify_saved_model_btn,
            settings_schemas=[HEIGHT_MAPPING_GROUP],
            height_mapping_content=self._height_mapping_content,
        )
        self._phase_tabs.append(tab)
        self._height_tab = tab
        return tab

    def set_height_mapping_content(self, widget: QWidget) -> None:
        self._height_mapping_content = widget
        if hasattr(self, "_height_tab"):
            self._height_tab.set_height_mapping_content(widget)

    def iter_save_settings_buttons(self):
        return [tab._save_button for tab in self._phase_tabs if getattr(tab, "_save_button", None) is not None]

    def set_settings_values(self, flat: dict) -> None:
        for tab in self._phase_tabs:
            tab.set_settings_values(flat)

    def get_settings_values(self) -> dict:
        values: dict = {}
        for tab in self._phase_tabs:
            values.update(tab.get_settings_values())
        return values

    def _build_system_tab(self) -> QWidget:
        return SystemCalibrationTab(
            sequence_btn=self.calibrate_sequence_btn,
            stop_btn=self.stop_robot_btn,
        )

    def toggle_crosshair(self) -> bool:
        self._crosshair_on = not self._crosshair_on
        self.crosshair_btn.setStyleSheet(
            APP_TOGGLE_ON_BUTTON_STYLE if self._crosshair_on else APP_TOGGLE_OFF_BUTTON_STYLE
        )
        return self._crosshair_on

    def toggle_magnifier(self) -> bool:
        self._magnifier_on = not self._magnifier_on
        self.magnifier_btn.setStyleSheet(
            APP_TOGGLE_ON_BUTTON_STYLE if self._magnifier_on else APP_TOGGLE_OFF_BUTTON_STYLE
        )
        return self._magnifier_on

    def set_stop_calibration_enabled(self, enabled: bool) -> None:
        self.stop_robot_btn.setEnabled(enabled)

    def set_test_calibration_enabled(self, enabled: bool) -> None:
        self.test_calibration_btn.setEnabled(enabled)

    def set_camera_tcp_offset_enabled(self, enabled: bool) -> None:
        self.calibrate_camera_tcp_offset_btn.setEnabled(enabled)

    def set_measure_marker_heights_enabled(self, enabled: bool) -> None:
        self.measure_marker_heights_btn.setEnabled(enabled)

    def set_depth_map_enabled(self, enabled: bool) -> None:
        self.verify_saved_model_btn.setEnabled(enabled)

    def set_laser_actions_enabled(self, enabled: bool) -> None:
        self.calibrate_laser_btn.setEnabled(enabled)
        self.detect_laser_btn.setEnabled(enabled)

    def set_enabled(self, enabled: bool) -> None:
        for button in (
            self.capture_btn,
            self.calibrate_camera_btn,
            self.calibrate_robot_btn,
            self.calibrate_sequence_btn,
        ):
            button.setEnabled(enabled)

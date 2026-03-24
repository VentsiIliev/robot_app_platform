from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from src.applications.calibration.view.calibration_styles import (
    _BTN_DANGER,
    _BTN_OVERLAY_OFF,
    _BTN_OVERLAY_ON,
    _BTN_PRIMARY,
    _BTN_SECONDARY,
    _BTN_SEQUENCE,
    _BTN_TEST,
    _CARD_STYLE,
    _LOG_STYLE,
    _PANEL_BG,
    divider,
    section_hint,
    section_label,
)


class CalibrationControlsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._crosshair_on = False
        self._magnifier_on = False
        self._build_ui()

    def _build_ui(self) -> None:
        content = QWidget()
        content.setStyleSheet(f"background: {_PANEL_BG};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        capture_card = QWidget()
        capture_card.setStyleSheet(_CARD_STYLE)
        capture_layout = QVBoxLayout(capture_card)
        capture_layout.setContentsMargins(16, 12, 16, 16)
        capture_layout.setSpacing(10)
        capture_layout.addWidget(section_label("Step 1: Setup"))
        capture_layout.addWidget(section_hint("Capture a fresh calibration image and enable overlays while defining the work area."))

        self.capture_btn = MaterialButton("Capture Calibration Image")
        self.capture_btn.setStyleSheet(_BTN_SECONDARY)
        capture_layout.addWidget(self.capture_btn)

        overlay_row = QHBoxLayout()
        overlay_row.setSpacing(8)
        self.crosshair_btn = MaterialButton("⊕  Crosshair")
        self.crosshair_btn.setStyleSheet(_BTN_OVERLAY_OFF)
        self.magnifier_btn = MaterialButton("🔍  Magnifier")
        self.magnifier_btn.setStyleSheet(_BTN_OVERLAY_OFF)
        overlay_row.addWidget(self.crosshair_btn)
        overlay_row.addWidget(self.magnifier_btn)
        capture_layout.addLayout(overlay_row)
        layout.addWidget(capture_card)

        calibration_card = QWidget()
        calibration_card.setStyleSheet(_CARD_STYLE)
        calibration_layout = QVBoxLayout(calibration_card)
        calibration_layout.setContentsMargins(16, 12, 16, 16)
        calibration_layout.setSpacing(10)
        calibration_layout.addWidget(section_label("Step 2: Camera and Robot Calibration"))
        calibration_layout.addWidget(section_hint("Run camera calibration, robot calibration, or the full sequence. TCP offset becomes available after calibration succeeds."))

        self.calibrate_camera_btn = MaterialButton("Calibrate Camera")
        self.calibrate_camera_btn.setStyleSheet(_BTN_PRIMARY)
        calibration_layout.addWidget(self.calibrate_camera_btn)

        self.calibrate_robot_btn = MaterialButton("Calibrate Robot")
        self.calibrate_robot_btn.setStyleSheet(_BTN_PRIMARY)
        calibration_layout.addWidget(self.calibrate_robot_btn)

        self.calibrate_camera_tcp_offset_btn = MaterialButton("Calibrate Camera TCP Offset")
        self.calibrate_camera_tcp_offset_btn.setStyleSheet(_BTN_PRIMARY)
        self.calibrate_camera_tcp_offset_btn.setEnabled(False)
        calibration_layout.addWidget(self.calibrate_camera_tcp_offset_btn)

        self.calibrate_sequence_btn = MaterialButton("Calibrate Camera → Robot")
        self.calibrate_sequence_btn.setStyleSheet(_BTN_SEQUENCE)
        calibration_layout.addWidget(self.calibrate_sequence_btn)

        calibration_layout.addWidget(divider())

        self.stop_robot_btn = MaterialButton("⏹  Stop Active Task")
        self.stop_robot_btn.setStyleSheet(_BTN_DANGER)
        self.stop_robot_btn.setEnabled(False)
        calibration_layout.addWidget(self.stop_robot_btn)
        layout.addWidget(calibration_card)

        height_card = QWidget()
        height_card.setStyleSheet(_CARD_STYLE)
        height_layout = QVBoxLayout(height_card)
        height_layout.setContentsMargins(16, 12, 16, 16)
        height_layout.setSpacing(10)
        height_layout.addWidget(section_label("Validation"))
        height_layout.addWidget(section_hint("Use a quick calibration test before moving on to area-based height workflows."))

        self.test_calibration_btn = MaterialButton("▶  Test Calibration")
        self.test_calibration_btn.setStyleSheet(_BTN_TEST)
        self.test_calibration_btn.setEnabled(False)
        height_layout.addWidget(self.test_calibration_btn)

        self.calibrate_laser_btn = MaterialButton("📡  Calibrate Laser")
        self.calibrate_laser_btn.setStyleSheet(_BTN_TEST)
        height_layout.addWidget(self.calibrate_laser_btn)

        self.detect_laser_btn = MaterialButton("🔎  Detect Laser Once")
        self.detect_laser_btn.setStyleSheet(_BTN_TEST)
        height_layout.addWidget(self.detect_laser_btn)

        self.measure_marker_heights_btn = MaterialButton("📏  Measure Marker Heights")
        self.measure_marker_heights_btn.setStyleSheet(_BTN_TEST)
        self.measure_marker_heights_btn.setEnabled(False)
        self.measure_marker_heights_btn.hide()

        self.verify_saved_model_btn = MaterialButton("🧪  Verify Saved Model")
        self.verify_saved_model_btn.setStyleSheet(_BTN_TEST)
        self.verify_saved_model_btn.setEnabled(False)
        height_layout.addWidget(self.verify_saved_model_btn)
        layout.addWidget(height_card)

        log_card = QWidget()
        log_card.setStyleSheet(_CARD_STYLE)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 12, 16, 16)
        log_layout.setSpacing(10)
        log_layout.addWidget(section_label("Activity"))
        log_layout.addWidget(section_hint("Live task output and verification reports appear here."))

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(_LOG_STYLE)
        self.log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        log_layout.addWidget(self.log, stretch=1)
        layout.addWidget(log_card, stretch=1)

        layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: {_PANEL_BG}; border-left: 1px solid #E0E0E0;")
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)

    def toggle_crosshair(self) -> bool:
        self._crosshair_on = not self._crosshair_on
        self.crosshair_btn.setStyleSheet(_BTN_OVERLAY_ON if self._crosshair_on else _BTN_OVERLAY_OFF)
        return self._crosshair_on

    def toggle_magnifier(self) -> bool:
        self._magnifier_on = not self._magnifier_on
        self.magnifier_btn.setStyleSheet(_BTN_OVERLAY_ON if self._magnifier_on else _BTN_OVERLAY_OFF)
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

    def append_log(self, message: str) -> None:
        self.log.append(message)

    def clear_log(self) -> None:
        self.log.clear()

    def set_enabled(self, enabled: bool) -> None:
        for button in (
            self.capture_btn,
            self.calibrate_camera_btn,
            self.calibrate_robot_btn,
            self.calibrate_sequence_btn,
        ):
            button.setEnabled(enabled)

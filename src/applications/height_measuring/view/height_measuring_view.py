from typing import List, Optional

import cv2
import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSplitter, QTextEdit,
    QVBoxLayout, QWidget, QMessageBox,
)
from src.applications.base.styled_message_box import show_warning
from src.applications.base.drawer_toggle import DrawerToggle
from src.applications.base.i_application_view import IApplicationView
from pl_gui.settings.settings_view.settings_view import SettingsView
from src.applications.base.robot_jog_widget import RobotJogWidget
from src.applications.height_measuring.view.height_measuring_schema import (
    CALIBRATION_GROUP, DETECTION_GROUP, MEASURING_GROUP,
)


class HeightMeasuringView(IApplicationView):

    calibrate_requested        = pyqtSignal()
    stop_requested             = pyqtSignal()
    save_settings_requested    = pyqtSignal()
    laser_on_requested         = pyqtSignal()
    laser_off_requested        = pyqtSignal()
    detect_once_requested      = pyqtSignal()
    start_continuous_requested = pyqtSignal()
    stop_continuous_requested  = pyqtSignal()
    jog_requested              = pyqtSignal(str, str, str, float)
    jog_stopped                = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("HeightMeasuring", parent)

    # ── IApplicationView contract ─────────────────────────────────────────────

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._settings_view = SettingsView(component_name="HeightMeasuring")
        self._settings_view.add_raw_tab("Measure",     self._build_measure_panel())
        self._settings_view.add_tab("Detection",   [DETECTION_GROUP])
        self._settings_view.add_tab("Calibration", [CALIBRATION_GROUP])
        self._settings_view.add_tab("Measuring",   [MEASURING_GROUP])
        layout.addWidget(self._settings_view)

        self._drawer = DrawerToggle(self, side="right", width=320)
        self._jog_widget = RobotJogWidget()
        self._drawer.add_widget(self._jog_widget)

        self._jog_widget.jog_requested.connect(self.jog_requested)
        self._jog_widget.jog_stopped.connect(self.jog_stopped)

        self._settings_view.save_requested.connect(self._on_inner_save)

    def can_close(self) -> bool:
        if hasattr(self, "_controller") and self._controller.is_calibrating():
            show_warning(
                self,
                "Calibration Running",
                "Calibration is currently running.\nPlease stop it before leaving.",
            )
            return False
        return True

    def clean_up(self) -> None:
        if hasattr(self, "_controller"):
            self._controller.stop()

    # ── Measure panel ─────────────────────────────────────────────────────────

    def _build_measure_panel(self) -> QWidget:
        panel = QWidget()
        root = QHBoxLayout(panel)
        root.setContentsMargins(8, 8, 8, 8)

        outer_splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(outer_splitter)

        # Left: vertical split — camera feed on top, mask below
        left = QSplitter(Qt.Orientation.Vertical)
        outer_splitter.addWidget(left)  # ← was missing: left had no Qt parent → GC'd

        self._frame_label = QLabel("No frame")
        self._frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._frame_label.setMinimumSize(480, 270)
        self._frame_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._frame_label.setStyleSheet("background: #111; color: #888;")
        left.addWidget(self._frame_label)

        self._mask_label = QLabel("No mask")
        self._mask_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mask_label.setMinimumSize(480, 180)
        self._mask_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._mask_label.setStyleSheet("background: #111; color: #888;")
        left.addWidget(self._mask_label)
        left.setStretchFactor(0, 2)
        left.setStretchFactor(1, 1)

        right = QWidget()  # ← goes directly into outer_splitter
        right.setMinimumWidth(280)
        right.setMaximumWidth(400)
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(8)
        right_layout.addWidget(self._build_status_group())
        right_layout.addWidget(self._build_laser_control_group())
        right_layout.addWidget(self._build_calibration_group())
        right_layout.addWidget(self._build_log_group(), 1)
        outer_splitter.addWidget(right)

        outer_splitter.setStretchFactor(0, 2)
        outer_splitter.setStretchFactor(1, 1)
        return panel

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("Status")
        layout = QVBoxLayout(group)
        self._status_label = QLabel("● Not Calibrated")
        self._status_label.setStyleSheet("color: #e55; font-weight: bold;")
        self._info_label = QLabel("")
        self._info_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        layout.addWidget(self._info_label)
        return group

    def _build_laser_control_group(self) -> QGroupBox:
        group = QGroupBox("Laser Control")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # Row 1: Turn On / Turn Off
        toggle_row = QHBoxLayout()
        self._btn_laser_on  = QPushButton("Turn On")
        self._btn_laser_off = QPushButton("Turn Off")
        self._btn_laser_off.setEnabled(False)
        toggle_row.addWidget(self._btn_laser_on)
        toggle_row.addWidget(self._btn_laser_off)
        layout.addLayout(toggle_row)

        # Detection sub-section label
        divider = QLabel("─── Detection ───────────────────")
        divider.setStyleSheet("color: #888; font-size: 8pt;")
        layout.addWidget(divider)

        # Row 2: Detect Once / Start Live / Stop Live
        detect_row = QHBoxLayout()
        self._btn_detect     = QPushButton("Detect Once")
        self._btn_start_live = QPushButton("Start Live")
        self._btn_stop_live  = QPushButton("Stop Live")
        self._btn_stop_live.setEnabled(False)
        detect_row.addWidget(self._btn_detect)
        detect_row.addWidget(self._btn_start_live)
        detect_row.addWidget(self._btn_stop_live)
        layout.addLayout(detect_row)

        # Detection result form
        form = QFormLayout()
        self._lbl_pixel_x = QLabel("—")
        self._lbl_pixel_y = QLabel("—")
        self._lbl_height  = QLabel("—")
        form.addRow("Pixel X:", self._lbl_pixel_x)
        form.addRow("Pixel Y:", self._lbl_pixel_y)
        form.addRow("Height:",  self._lbl_height)
        layout.addLayout(form)

        self._btn_laser_on.clicked.connect(self._on_laser_on_clicked)
        self._btn_laser_off.clicked.connect(self._on_laser_off_clicked)
        self._btn_detect.clicked.connect(self._on_detect_clicked)
        self._btn_start_live.clicked.connect(self._on_start_continuous_clicked)
        self._btn_stop_live.clicked.connect(self._on_stop_continuous_clicked)
        return group

    def _build_calibration_group(self) -> QGroupBox:
        group = QGroupBox("Calibration Start Position")
        layout = QVBoxLayout(group)

        form = QFormLayout()
        self._spin_x  = self._make_spin(-5000, 5000)
        self._spin_y  = self._make_spin(-5000, 5000)
        self._spin_z  = self._make_spin(-5000, 5000)
        self._spin_rx = self._make_spin(-360,   360)
        self._spin_ry = self._make_spin(-360,   360)
        self._spin_rz = self._make_spin(-360,   360)
        form.addRow("X (mm):",  self._spin_x)
        form.addRow("Y (mm):",  self._spin_y)
        form.addRow("Z (mm):",  self._spin_z)
        form.addRow("RX (°):",  self._spin_rx)
        form.addRow("RY (°):",  self._spin_ry)
        form.addRow("RZ (°):",  self._spin_rz)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self._btn_calibrate = QPushButton("Calibrate")
        self._btn_stop      = QPushButton("Stop")
        self._btn_stop.setEnabled(False)
        btn_row.addWidget(self._btn_calibrate)
        btn_row.addWidget(self._btn_stop)
        layout.addLayout(btn_row)

        self._btn_calibrate.clicked.connect(self._on_calibrate_clicked)
        self._btn_stop.clicked.connect(self._on_stop_clicked)
        return group

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("Log")
        layout = QVBoxLayout(group)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log)
        return group

    @staticmethod
    def _make_spin(min_val: float, max_val: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(min_val, max_val)
        s.setDecimals(3)
        s.setSingleStep(0.1)
        return s

    # ── Named signal forwarders ───────────────────────────────────────────────

    def _on_calibrate_clicked(self) -> None:
        self.calibrate_requested.emit()

    def _on_stop_clicked(self) -> None:
        self.stop_requested.emit()

    def _on_inner_save(self, _values: dict) -> None:
        self.save_settings_requested.emit()

    def _on_laser_on_clicked(self) -> None:
        self.laser_on_requested.emit()

    def _on_laser_off_clicked(self) -> None:
        self.laser_off_requested.emit()

    def _on_detect_clicked(self) -> None:
        self.detect_once_requested.emit()

    def _on_start_continuous_clicked(self) -> None:
        self.start_continuous_requested.emit()

    def _on_stop_continuous_clicked(self) -> None:
        self.stop_continuous_requested.emit()

    # ── Setters ───────────────────────────────────────────────────────────────

    def set_mask_frame(self, mask: np.ndarray) -> None:
        # mask is (H, W) uint8 — convert to RGB for display
        rgb = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(bytes(rgb.data), w, h, ch * w, QImage.Format.Format_RGB888)
        self._mask_label.setPixmap(
            QPixmap.fromImage(qimg).scaled(
                self._mask_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def set_frame(self, frame: np.ndarray) -> None:
        h, w, ch = frame.shape
        qimg = QImage(bytes(frame.data), w, h, ch * w, QImage.Format.Format_RGB888)
        self._frame_label.setPixmap(
            QPixmap.fromImage(qimg).scaled(
                self._frame_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def set_calibration_status(self, is_calibrated: bool, info: Optional[dict]) -> None:
        if is_calibrated:
            self._status_label.setText("● Calibrated")
            self._status_label.setStyleSheet("color: #5e5; font-weight: bold;")
            if info:
                self._info_label.setText(
                    f"Degree: {info.get('degree', '?')}  |  "
                    f"MSE: {info.get('mse', 0.0):.4f}  |  "
                    f"Points: {info.get('points', '?')}"
                )
        else:
            self._status_label.setText("● Not Calibrated")
            self._status_label.setStyleSheet("color: #e55; font-weight: bold;")
            self._info_label.setText("")

    def set_calibrating(self, running: bool) -> None:
        self._btn_calibrate.setEnabled(not running)
        self._btn_stop.setEnabled(running)
        self._btn_detect.setEnabled(not running)  # ← new
        self._btn_start_live.setEnabled(not running)  # ← new

    def set_laser_state(self, on: bool) -> None:
        self._btn_laser_on.setEnabled(not on)
        self._btn_laser_off.setEnabled(on)

    def set_live_detecting(self, running: bool) -> None:
        self._btn_start_live.setEnabled(not running)
        self._btn_stop_live.setEnabled(running)
        self._btn_detect.setEnabled(not running)
        self._btn_calibrate.setEnabled(not running)  # ← new
        self._btn_laser_on.setEnabled(not running)
        self._btn_laser_off.setEnabled(not running)

    def set_detect_result(self, result) -> None:
        if result.pixel_coords is not None:
            x, y = result.pixel_coords
            self._lbl_pixel_x.setText(f"{x:.1f}")
            self._lbl_pixel_y.setText(f"{y:.1f}")
        else:
            self._lbl_pixel_x.setText("—")
            self._lbl_pixel_y.setText("—")

        if result.height_mm is not None:
            self._lbl_height.setText(f"{result.height_mm:.2f} mm")
        else:
            self._lbl_height.setText("—")

    def set_mask_frame_rgb(self, rgb: np.ndarray) -> None:
        h, w, ch = rgb.shape
        qimg = QImage(bytes(rgb.data), w, h, ch * w, QImage.Format.Format_RGB888)
        self._mask_label.setPixmap(
            QPixmap.fromImage(qimg).scaled(
                self._mask_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def set_settings(self, settings) -> None:
        pos = settings.calibration.calibration_initial_position
        for spin, val in zip(
            [self._spin_x, self._spin_y, self._spin_z, self._spin_rx, self._spin_ry, self._spin_rz],
            pos[:6],
        ):
            spin.setValue(val)

    def load_settings(self, flat: dict) -> None:
        self._settings_view.set_values(flat)

    def get_settings_values(self) -> dict:
        return self._settings_view.get_values()

    def get_initial_position(self) -> List[float]:
        return [
            self._spin_x.value(), self._spin_y.value(), self._spin_z.value(),
            self._spin_rx.value(), self._spin_ry.value(), self._spin_rz.value(),
        ]

    def append_log(self, message: str) -> None:
        self._log.append(message)

    def set_jog_position(self, pos: list) -> None:
        self._jog_widget.set_position(pos)

    def show_message(self, message: str, is_error: bool = False) -> None:
        colour = "#e55" if is_error else "#5e5"
        self._log.append(f'<span style="color:{colour}">{message}</span>')

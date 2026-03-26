from typing import List, Optional

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDoubleSpinBox, QFormLayout, QGroupBox,
    QLabel, QVBoxLayout, QWidget, QMessageBox,
)
from src.applications.base.styled_message_box import show_warning
from src.applications.base.collapsible_settings_view import CollapsibleSettingsView
from src.applications.base.app_styles import emphasis_text_style
from src.applications.base.i_application_view import IApplicationView
from src.applications.height_measuring.view.height_measuring_schema import (
    CALIBRATION_GROUP, DETECTION_GROUP, MEASURING_GROUP,
)


class HeightMeasuringView(IApplicationView):
    SHOW_JOG_WIDGET = True
    JOG_FRAME_SELECTOR_ENABLED = True

    save_settings_requested    = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("HeightMeasuring", parent)

    # ── IApplicationView contract ─────────────────────────────────────────────

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._settings_view = CollapsibleSettingsView(component_name="HeightMeasuring")
        self._settings_view.add_raw_tab("Overview", self._build_overview_panel())
        self._settings_view.add_tab("Detection",   [DETECTION_GROUP])
        self._settings_view.add_tab("Calibration", [CALIBRATION_GROUP])
        self._settings_view.add_tab("Measuring",   [MEASURING_GROUP])
        layout.addWidget(self._settings_view)

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

    def _build_overview_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(self._build_status_group())
        layout.addWidget(self._build_calibration_group())
        layout.addStretch(1)
        return panel

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("Status")
        layout = QVBoxLayout(group)
        self._status_label = QLabel("● Not Calibrated")
        self._status_label.setStyleSheet(emphasis_text_style(color="#e55"))
        self._info_label = QLabel("")
        self._info_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        layout.addWidget(self._info_label)
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

        return group

    @staticmethod
    def _make_spin(min_val: float, max_val: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(min_val, max_val)
        s.setDecimals(3)
        s.setSingleStep(0.1)
        return s

    # ── Named signal forwarders ───────────────────────────────────────────────

    def _on_inner_save(self, _values: dict) -> None:
        self.save_settings_requested.emit()

    # ── Setters ───────────────────────────────────────────────────────────────

    def set_calibration_status(self, is_calibrated: bool, info: Optional[dict]) -> None:
        if is_calibrated:
            self._status_label.setText("● Calibrated")
            self._status_label.setStyleSheet(emphasis_text_style(color="#5e5"))
            if info:
                self._info_label.setText(
                    f"Degree: {info.get('degree', '?')}  |  "
                    f"MSE: {info.get('mse', 0.0):.4f}  |  "
                    f"Points: {info.get('points', '?')}"
                )
        else:
            self._status_label.setText("● Not Calibrated")
            self._status_label.setStyleSheet(emphasis_text_style(color="#e55"))
            self._info_label.setText("")

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

    def show_message(self, message: str, is_error: bool = False) -> None:
        if is_error:
            QMessageBox.warning(self, "Height Measuring Settings", message)
        else:
            QMessageBox.information(self, "Height Measuring Settings", message)

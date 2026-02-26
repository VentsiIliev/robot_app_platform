from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel

from pl_gui.settings.settings_view.settings_view import SettingsView
from pl_gui.settings.settings_view.styles import (
    BG_COLOR, ACTION_BTN_STYLE, LABEL_STYLE, BORDER, PRIMARY,
)
from src.plugins.glue_cell_settings.view.cell_monitor_widget import CellMonitorWidget
from src.plugins.glue_cell_settings.view.glue_cell_schema import (
    CONNECTION_GROUP, CALIBRATION_GROUP, MEASUREMENT_GROUP,
)


class CellSettingsTab(QWidget):

    save_requested = pyqtSignal(dict)
    tare_requested = pyqtSignal()

    def __init__(self, cell_id: int, parent=None):
        super().__init__(parent)
        self._cell_id = cell_id
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Live monitor bar ─────────────────────────────────────────
        monitor_row = QHBoxLayout()
        monitor_row.setContentsMargins(12, 6, 12, 6)
        monitor_row.setSpacing(12)

        cell_label = QLabel(f"Cell {self._cell_id}")
        cell_label.setStyleSheet(LABEL_STYLE)
        monitor_row.addWidget(cell_label)

        self._monitor = CellMonitorWidget()
        monitor_row.addWidget(self._monitor, stretch=1)

        tare_btn = QPushButton("⊘  Tare")
        tare_btn.setFixedWidth(100)
        tare_btn.setStyleSheet(ACTION_BTN_STYLE)
        tare_btn.clicked.connect(self.tare_requested.emit)
        monitor_row.addWidget(tare_btn)

        monitor_bar = QWidget()
        monitor_bar.setLayout(monitor_row)
        monitor_bar.setStyleSheet(
            f"background-color: white; border-bottom: 1px solid {BORDER};"
        )
        monitor_bar.setFixedHeight(56)
        root.addWidget(monitor_bar)

        # ── Settings form ────────────────────────────────────────────
        self._settings_view = SettingsView(
            component_name=f"CellSettings_{self._cell_id}",
            mapper=lambda cfg: cfg,
        )
        self._settings_view.add_tab("Connection",  [CONNECTION_GROUP])
        self._settings_view.add_tab("Calibration", [CALIBRATION_GROUP])
        self._settings_view.add_tab("Measurement",  [MEASUREMENT_GROUP])
        self._settings_view.save_requested.connect(
            lambda _: self.save_requested.emit(self._settings_view.get_values())
        )
        root.addWidget(self._settings_view)

    def load(self, flat: dict) -> None:
        self._settings_view.load(flat)

    def set_weight(self, value: float) -> None:
        self._monitor.set_weight(value)

    def set_state(self, state: str) -> None:
        self._monitor.set_state(state)

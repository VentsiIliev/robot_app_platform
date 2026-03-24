from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.applications.base.collapsible_settings_view import CollapsibleSettingsView
from pl_gui.settings.settings_view.styles import ACTION_BTN_STYLE, BG_COLOR, BORDER, LABEL_STYLE
from src.applications.glue_cell_settings.view.cell_monitor_widget import CellMonitorWidget
from src.robot_systems.glue.applications.dispense_channel_settings.view.dispense_channel_schema import (
    CALIBRATION_GROUP,
    MEASUREMENT_GROUP,
    SCALE_GROUP,
    build_glue_group,
)
from src.shared_contracts.declarations import DispenseChannelDefinition


class DispenseChannelTab(QWidget):
    save_requested = pyqtSignal(str, dict)
    tare_requested = pyqtSignal(str)
    pump_on_requested = pyqtSignal(str)
    pump_off_requested = pyqtSignal(str)

    def __init__(self, definition: DispenseChannelDefinition, glue_types: list[str], parent=None):
        super().__init__(parent)
        self._definition = definition
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self._build_ui(glue_types)

    def _build_ui(self, glue_types: list[str]) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        monitor_row = QHBoxLayout()
        monitor_row.setContentsMargins(12, 6, 12, 6)
        monitor_row.setSpacing(12)

        title = QLabel(self._definition.label or self._definition.id)
        title.setStyleSheet(LABEL_STYLE)
        monitor_row.addWidget(title)

        meta = QLabel(
            f"Cell {self._definition.weight_cell_id} | Pump {self._definition.pump_motor_address}"
        )
        meta.setStyleSheet("QLabel { color: #666666; font-size: 10pt; background: transparent; }")
        monitor_row.addWidget(meta)

        self._monitor = CellMonitorWidget()
        monitor_row.addWidget(self._monitor, stretch=1)

        tare_btn = QPushButton("Tare")
        tare_btn.setStyleSheet(ACTION_BTN_STYLE)
        tare_btn.clicked.connect(self._on_tare_clicked)
        monitor_row.addWidget(tare_btn)

        pump_on_btn = QPushButton("Pump On")
        pump_on_btn.setStyleSheet(ACTION_BTN_STYLE)
        pump_on_btn.clicked.connect(self._on_pump_on_clicked)
        monitor_row.addWidget(pump_on_btn)

        pump_off_btn = QPushButton("Pump Off")
        pump_off_btn.setStyleSheet(ACTION_BTN_STYLE)
        pump_off_btn.clicked.connect(self._on_pump_off_clicked)
        monitor_row.addWidget(pump_off_btn)

        monitor_bar = QWidget()
        monitor_bar.setLayout(monitor_row)
        monitor_bar.setStyleSheet(
            f"background-color: white; border-bottom: 1px solid {BORDER};"
        )
        monitor_bar.setFixedHeight(56)
        root.addWidget(monitor_bar)

        self._settings_view = CollapsibleSettingsView(
            component_name=f"DispenseChannelSettings_{self._definition.id}",
            mapper=lambda cfg: cfg,
        )
        self._settings_view.add_tab("Glue", [build_glue_group(glue_types)])
        self._settings_view.add_tab("Scale", [SCALE_GROUP])
        self._settings_view.add_tab("Calibration", [CALIBRATION_GROUP])
        self._settings_view.add_tab("Measurement", [MEASUREMENT_GROUP])
        self._settings_view.save_requested.connect(self._on_save_requested)
        root.addWidget(self._settings_view)

    def load(self, flat: dict) -> None:
        self._settings_view.load(flat)

    def set_weight(self, value: float) -> None:
        self._monitor.set_weight(value)

    def set_state(self, state: str) -> None:
        self._monitor.set_state(state)

    def _on_save_requested(self, _payload=None) -> None:
        self.save_requested.emit(self._definition.id, self._settings_view.get_values())

    def _on_tare_clicked(self) -> None:
        self.tare_requested.emit(self._definition.id)

    def _on_pump_on_clicked(self) -> None:
        self.pump_on_requested.emit(self._definition.id)

    def _on_pump_off_clicked(self) -> None:
        self.pump_off_requested.emit(self._definition.id)

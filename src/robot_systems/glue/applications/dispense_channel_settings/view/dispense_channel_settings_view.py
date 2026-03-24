from __future__ import annotations

from typing import Dict, List

from PyQt6.QtCore import QEvent, pyqtSignal
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout

from pl_gui.settings.settings_view.styles import BG_COLOR, TAB_WIDGET_STYLE
from src.applications.base.i_application_view import IApplicationView
from src.robot_systems.glue.applications.dispense_channel_settings.view.dispense_channel_tab import (
    DispenseChannelTab,
)
from src.shared_contracts.declarations import DispenseChannelDefinition


class DispenseChannelSettingsView(IApplicationView):
    save_requested = pyqtSignal(str, dict)
    tare_requested = pyqtSignal(str)
    pump_on_requested = pyqtSignal(str)
    pump_off_requested = pyqtSignal(str)

    def __init__(self, channel_definitions: List[DispenseChannelDefinition], glue_types: list[str], parent=None):
        self._channel_definitions = channel_definitions
        self._glue_types = list(glue_types)
        self._tabs: Dict[str, DispenseChannelTab] = {}
        super().__init__("DispenseChannelSettings", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet(TAB_WIDGET_STYLE)

        for definition in self._channel_definitions:
            tab = DispenseChannelTab(definition, self._glue_types)
            tab.save_requested.connect(self.save_requested.emit)
            tab.tare_requested.connect(self.tare_requested.emit)
            tab.pump_on_requested.connect(self.pump_on_requested.emit)
            tab.pump_off_requested.connect(self.pump_off_requested.emit)
            self._tabs[definition.id] = tab
            self._tab_widget.addTab(tab, definition.label or definition.id)

        layout.addWidget(self._tab_widget)

    def load_channel(self, channel_id: str, flat: dict) -> None:
        tab = self._tabs.get(channel_id)
        if tab is not None:
            tab.load(flat)

    def set_channel_weight(self, channel_id: str, value: float) -> None:
        tab = self._tabs.get(channel_id)
        if tab is not None:
            tab.set_weight(value)

    def set_channel_state(self, channel_id: str, state: str) -> None:
        tab = self._tabs.get(channel_id)
        if tab is not None:
            tab.set_state(state)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass

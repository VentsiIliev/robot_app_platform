from __future__ import annotations

from typing import Dict, List

from PyQt6.QtCore import pyqtSignal, QEvent
from PyQt6.QtWidgets import QVBoxLayout, QTabWidget

from pl_gui.settings.settings_view.styles import TAB_WIDGET_STYLE, BG_COLOR
from src.applications.base.i_application_view import IApplicationView
from src.applications.glue_cell_settings.view.cell_settings_tab import CellSettingsTab


class GlueCellSettingsView(IApplicationView):

    save_requested = pyqtSignal(int, dict)
    tare_requested = pyqtSignal(int)

    def __init__(self, cell_ids: List[int], parent=None):
        self._cell_ids = cell_ids
        self._tabs: Dict[int, CellSettingsTab] = {}
        super().__init__("GlueCellSettings", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet(TAB_WIDGET_STYLE)

        for cell_id in self._cell_ids:
            tab = CellSettingsTab(cell_id)
            tab.save_requested.connect(lambda flat, cid=cell_id: self.save_requested.emit(cid, flat))
            tab.tare_requested.connect(lambda cid=cell_id: self.tare_requested.emit(cid))
            self._tabs[cell_id] = tab
            self._tab_widget.addTab(tab, f"Cell {cell_id}")

        layout.addWidget(self._tab_widget)

    def load_cell(self, cell_id: int, flat: dict) -> None:
        tab = self._tabs.get(cell_id)
        if tab:
            tab.load(flat)

    def set_cell_weight(self, cell_id: int, value: float) -> None:
        tab = self._tabs.get(cell_id)
        if tab:
            tab.set_weight(value)

    def set_cell_state(self, cell_id: int, state: str) -> None:
        tab = self._tabs.get(cell_id)
        if tab:
            tab.set_state(state)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass

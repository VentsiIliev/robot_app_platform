from PyQt6.QtWidgets import (
    QGroupBox, QGridLayout, QVBoxLayout, QWidget,
    QLabel, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal

from src.settings.settings_view.schema import SettingGroup, SettingField
from src.settings.settings_view.styles import GROUP_STYLE, LABEL_STYLE
from src.settings.settings_view.widget_factory import get_handler, WidgetHandler


class GenericSettingGroup(QGroupBox):
    """
    Schema-driven QGroupBox — touch-friendly, 2-column grid.

    Layout per field:
        ┌─────────────┐  ┌─────────────┐
        │ Label       │  │ Label       │
        │ [  widget ] │  │ [  widget ] │
        └─────────────┘  └─────────────┘

    Fields whose handler has full_width=True always span both columns.

    Signals:
        value_changed(key: str, value: object)
    """

    value_changed = pyqtSignal(str, object)

    def __init__(self, group: SettingGroup, parent=None):
        super().__init__(group.title, parent)
        self.setStyleSheet(GROUP_STYLE)
        self._group = group
        self._widgets:  dict[str, QWidget]        = {}
        self._handlers: dict[str, WidgetHandler]  = {}
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout()
        outer.setContentsMargins(12, 16, 12, 12)
        outer.setSpacing(0)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        row = 0
        col = 0
        for f in self._group.fields:
            handler = get_handler(f.widget_type)

            cell = QWidget()
            cell.setStyleSheet("background: transparent;")
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(6)

            label = QLabel(f.label)
            label.setStyleSheet(LABEL_STYLE)
            cell_layout.addWidget(label)

            emit = lambda val, k=f.key: self.value_changed.emit(k, val)
            widget = handler.create(f, emit)
            cell_layout.addWidget(widget)

            self._widgets[f.key]  = widget
            self._handlers[f.key] = handler

            if handler.full_width:
                if col == 1:
                    row += 1
                grid.addWidget(cell, row, 0, 1, 2)
                row += 1
                col = 0
            else:
                grid.addWidget(cell, row, col)
                col += 1
                if col == 2:
                    col = 0
                    row += 1

        outer.addLayout(grid)
        self.setLayout(outer)

    # ── public API ────────────────────────────────────────────────────────────

    def set_values(self, values: dict) -> None:
        for key, widget in self._widgets.items():
            if key not in values:
                continue
            widget.blockSignals(True)
            try:
                self._handlers[key].set_value(widget, values[key])
            finally:
                widget.blockSignals(False)

    def get_values(self) -> dict:
        return {
            key: self._handlers[key].get_value(widget)
            for key, widget in self._widgets.items()
        }

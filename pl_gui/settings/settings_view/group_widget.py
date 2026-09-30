from PyQt6.QtWidgets import (
    QGroupBox, QGridLayout, QVBoxLayout, QWidget,
    QLabel, QSizePolicy
)
from PyQt6.QtCore import QCoreApplication, QEvent, pyqtSignal

from pl_gui.settings.settings_view.schema import SettingGroup, SettingField
from pl_gui.settings.settings_view.styles import (
    GROUP_STYLE, LABEL_STYLE, SETTINGS_FIELD_LABEL_STYLE,
)
from pl_gui.settings.settings_view.widget_factory import get_handler, WidgetHandler


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

    def __init__(self, group: SettingGroup, parent=None, *, compact: bool = False):
        super().__init__(group.title, parent)
        self.setStyleSheet(GROUP_STYLE)
        self._group = group
        self._compact = compact
        self._widgets:  dict[str, QWidget]        = {}
        self._handlers: dict[str, WidgetHandler]  = {}
        self._axis_headers: list[tuple[QLabel, str]] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout()
        outer.setContentsMargins(0 if self._compact else 12, 0 if self._compact else 16,
                                 0 if self._compact else 12, 0 if self._compact else 12)
        outer.setSpacing(0)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12 if self._compact else 16)
        axis_pairs = self._group.axis_pairs and self._compact
        column_count = max(1, int(getattr(self._group, "columns", 2) or 2))
        if axis_pairs:
            grid.setColumnMinimumWidth(0, 68)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(2, 1)
            for col, title in enumerate(("AXIS", "MINIMUM", "MAXIMUM")):
                label = QLabel(self._axis_text(title))
                label.setStyleSheet(SETTINGS_FIELD_LABEL_STYLE)
                self._axis_headers.append((label, title))
                grid.addWidget(label, 0, col)
        else:
            for idx in range(column_count):
                grid.setColumnStretch(idx, 1)

        def make_cell(f: SettingField, *, show_label: bool = True):
            handler = get_handler(f.widget_type)

            cell = QWidget()
            cell.setStyleSheet("background: transparent;")
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(4 if self._compact else 6)

            if show_label and f.widget_type != "checkbox_string":
                label = QLabel(f.label.upper() if self._compact else f.label)
                label.setStyleSheet(SETTINGS_FIELD_LABEL_STYLE if self._compact else LABEL_STYLE)
                cell_layout.addWidget(label)

            emit = lambda val, k=f.key: self.value_changed.emit(k, val)
            widget = handler.create(f, emit)
            cell_layout.addWidget(widget)

            self._widgets[f.key]  = widget
            self._handlers[f.key] = handler
            return cell, handler

        if axis_pairs:
            for row, index in enumerate(range(0, len(self._group.fields), 2), start=1):
                pair = self._group.fields[index:index + 2]
                axis = QLabel(pair[0].label.split()[0].upper())
                axis.setStyleSheet(LABEL_STYLE)
                grid.addWidget(axis, row, 0)
                for col, field in enumerate(pair, start=1):
                    cell, _handler = make_cell(field, show_label=False)
                    grid.addWidget(cell, row, col)
        else:
            row = 0
            col = 0
            for f in self._group.fields:
                cell, handler = make_cell(f)

                if handler.full_width:
                    if col != 0:
                        row += 1
                    grid.addWidget(cell, row, 0, 1, column_count)
                    row += 1
                    col = 0
                else:
                    grid.addWidget(cell, row, col)
                    col += 1
                    if col == column_count:
                        col = 0
                        row += 1

        outer.addLayout(grid)
        self.setLayout(outer)

    @staticmethod
    def _axis_text(source: str) -> str:
        return QCoreApplication.translate("SettingsView", source) or source

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            for label, source in getattr(self, "_axis_headers", []):
                label.setText(self._axis_text(source))
        super().changeEvent(event)

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

    def set_step(self, step: float) -> None:
        for widget in self._widgets.values():
            if hasattr(widget, "setSingleStep"):
                widget.setSingleStep(step)

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from pl_gui.settings.settings_view.schema import SettingField, SettingGroup
from pl_gui.settings.settings_view.styles import (
    BORDER, PRIMARY, SECONDARY_BG, TEXT_COLOR,
)
from src.applications.base.widgets.custom_virtual_keyboard import (
    KeyboardLineEdit,
)
from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField


_INPUT_STYLE = f"""
QLineEdit, QComboBox {{
    background: white; color: {TEXT_COLOR}; border: 1px solid {BORDER};
    border-radius: 6px; min-height: 36px; padding: 0 8px;
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {PRIMARY};
}}
"""


class _IntListEditor(QWidget):
    def __init__(self, field: SettingField, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._list = QListWidget()
        self._list.setFixedHeight(68)
        self._list.setFlow(QListWidget.Flow.LeftToRight)
        self._list.setWrapping(True)
        self._list.setStyleSheet(
            f"QListWidget {{ background: white; border: 1px solid {BORDER}; "
            f"border-radius: 6px; color: {TEXT_COLOR}; }}"
            f"QListWidget::item {{ background: {SECONDARY_BG}; padding: 3px 7px; margin: 4px; }}"
            f"QListWidget::item:selected {{ background: {PRIMARY}; color: white; }}"
        )
        layout.addWidget(self._list)
        row = QHBoxLayout()
        row.setSpacing(8)
        self._input = KeyboardNumberField()
        self._input.setRange(int(field.min_val), int(field.max_val))
        row.addWidget(self._input, stretch=1)
        add_button = QPushButton("Add")
        add_button.clicked.connect(self._add)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._remove)
        for button in (add_button, remove_button):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(38)
            button.setStyleSheet(
                f"QPushButton {{ color: {PRIMARY}; background: {SECONDARY_BG}; "
                "border: none; border-radius: 6px; padding: 0 12px; }"
            )
            row.addWidget(button)
        layout.addLayout(row)
        self.set_ids(field.default or "")

    def _add(self) -> None:
        self._list.addItem(str(self._input.value()))

    def _remove(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)

    def get_ids(self) -> list[int]:
        return [int(self._list.item(index).text()) for index in range(self._list.count())]

    def set_ids(self, value) -> None:
        self._list.clear()
        values = value.split(",") if isinstance(value, str) else value
        for item in values:
            try:
                number = int(str(item).strip())
            except ValueError:
                continue
            self._list.addItem(str(number))


class CompactSettingsGroup(QWidget):
    """Compact editor for calibration SettingGroup values."""

    def __init__(self, schema: SettingGroup, parent=None):
        super().__init__(parent)
        self._fields = {field.key: field for field in schema.fields}
        self._editors: dict[str, QWidget] = {}
        columns = 3 if len(schema.fields) > 4 else 2
        grid = QGridLayout(self)
        grid.setContentsMargins(4, 12, 4, 4)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        for column in range(columns):
            grid.setColumnStretch(column, 1)
        row = column = 0
        for field in schema.fields:
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(6)
            label = QLabel(field.label)
            label.setStyleSheet(f"color: {PRIMARY}; font-size: 9pt; background: transparent;")
            cell_layout.addWidget(label)
            editor = self._make_editor(field)
            editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self._editors[field.key] = editor
            cell_layout.addWidget(editor)
            wide = field.widget_type == "int_list"
            if wide and column:
                row += 1
                column = 0
            grid.addWidget(cell, row, column, 1, columns if wide else 1)
            if wide:
                row += 1
            else:
                column += 1
                if column == columns:
                    row += 1
                    column = 0
        grid.setRowStretch(row + 1, 1)

    @staticmethod
    def _make_editor(field: SettingField) -> QWidget:
        if field.widget_type in ("spinbox", "double_spinbox"):
            editor = KeyboardNumberField(decimal=field.widget_type == "double_spinbox")
            editor.setRange(field.min_val, field.max_val)
            if field.widget_type == "double_spinbox":
                editor.setDecimals(field.decimals)
            editor.setSingleStep(field.step)
            editor.setSuffix(field.suffix)
            editor.setValue(field.default or 0)
            return editor
        if field.widget_type == "int_list":
            return _IntListEditor(field)
        if field.widget_type == "combo" and set(field.choices or []) == {"True", "False"}:
            editor = QCheckBox()
            editor.setChecked(str(field.default) == "True")
            editor.setCursor(Qt.CursorShape.PointingHandCursor)
            editor.setStyleSheet(
                "QCheckBox { min-height: 38px; background: transparent; }"
                f"QCheckBox::indicator {{ width: 44px; height: 24px; border-radius: 12px; "
                f"border: 1px solid {BORDER}; background: {SECONDARY_BG}; }}"
                f"QCheckBox::indicator:checked {{ background: {PRIMARY}; border-color: {PRIMARY}; }}"
            )
            return editor
        if field.widget_type == "combo":
            editor = QComboBox()
            editor.addItems(field.choices or [])
            editor.setCurrentText(str(field.default))
        elif field.widget_type == "line_edit":
            editor = KeyboardLineEdit()
            editor.setText(str(field.default or ""))
        else:
            raise ValueError(f"Unsupported calibration field: {field.widget_type}")
        editor.setStyleSheet(_INPUT_STYLE)
        return editor

    def set_values(self, values: dict) -> None:
        for key, value in values.items():
            editor = self._editors.get(key)
            if editor is None:
                continue
            field = self._fields[key]
            if field.widget_type in ("spinbox", "double_spinbox"):
                editor.setValue(value)
            elif field.widget_type == "int_list":
                editor.set_ids(value)
            elif isinstance(editor, QCheckBox):
                editor.setChecked(str(value) == "True")
            elif isinstance(editor, QComboBox):
                editor.setCurrentText(str(value))
            else:
                editor.setText(str(value))

    def get_values(self) -> dict:
        values = {}
        for key, editor in self._editors.items():
            field = self._fields[key]
            if field.widget_type in ("spinbox", "double_spinbox"):
                values[key] = editor.value()
            elif field.widget_type == "int_list":
                values[key] = editor.get_ids()
            elif isinstance(editor, QCheckBox):
                values[key] = "True" if editor.isChecked() else "False"
            elif isinstance(editor, QComboBox):
                values[key] = editor.currentText()
            else:
                values[key] = editor.text()
        return values

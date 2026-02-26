"""
Pure UI tab for managing custom glue types.

Built-in types (Type A–D) are always shown, read-only, italic.
Custom types are loaded via load_types() and can be added / edited / removed.

Signals (connect to your repo calls from the controller):
    add_requested(name, description)
    update_requested(id, name, description)
    remove_requested(id)
"""
from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from src.robot_apps.glue.settings.glue_types import Glue as GlueType
from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE, BG_COLOR, BORDER, GHOST_BTN_STYLE,
    GROUP_STYLE, LABEL_STYLE, PRIMARY,
)


_TABLE_STYLE = f"""
QTableWidget {{
    background: white;
    border: none;
    font-size: 11pt;
    color: #333333;
    gridline-color: {BORDER};
}}
QTableWidget::item {{ padding: 8px 12px; }}
QTableWidget::item:selected {{
    background: rgba(144, 91, 169, 0.12);
    color: #333333;
}}
QHeaderView::section {{
    background: {BG_COLOR};
    color: #555555;
    font-size: 10pt;
    font-weight: bold;
    border: none;
    border-bottom: 2px solid {BORDER};
    padding: 8px 12px;
}}
"""

_INPUT_STYLE = f"""
QLineEdit {{
    background: white;
    color: #333333;
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 11pt;
    min-height: 44px;
}}
QLineEdit:focus {{ border-color: {PRIMARY}; }}
"""


class GlueTypeTab(QWidget):
    """
    Tab widget for managing custom glue types.

    Built-in types are fixed and shown in italic.
    Custom types support Add / Edit / Remove via an inline form (no dialog).
    """

    add_requested    = pyqtSignal(str, str)       # name, description
    update_requested = pyqtSignal(str, str, str)  # id, name, description
    remove_requested = pyqtSignal(str)            # id

    BUILTIN_TYPES = ["Type A", "Type B", "Type C", "Type D"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._custom_types: List[GlueType] = []
        self._editing_id: str | None = None
        self._build_ui()
        self._hide_form()
        self._refresh_table()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        layout.addWidget(self._build_table_group())
        layout.addWidget(self._build_form_group())
        layout.addStretch()

    def _build_table_group(self) -> QGroupBox:
        group = QGroupBox("Glue Types")
        group.setStyleSheet(GROUP_STYLE)
        inner = QVBoxLayout(group)
        inner.setContentsMargins(12, 16, 12, 12)
        inner.setSpacing(12)

        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Name", "Description"])
        self._table.setStyleSheet(_TABLE_STYLE)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setMinimumHeight(280)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        inner.addWidget(self._table)

        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self._btn_add = QPushButton("Add")
        self._btn_add.setStyleSheet(GHOST_BTN_STYLE)
        self._btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add.clicked.connect(self._start_add)

        self._btn_edit = QPushButton("Edit")
        self._btn_edit.setStyleSheet(GHOST_BTN_STYLE)
        self._btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_edit.setEnabled(False)
        self._btn_edit.clicked.connect(self._start_edit)

        self._btn_remove = QPushButton("Remove")
        self._btn_remove.setStyleSheet(ACTION_BTN_STYLE)
        self._btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_remove.setEnabled(False)
        self._btn_remove.clicked.connect(self._on_remove)

        btn_layout.addWidget(self._btn_add)
        btn_layout.addWidget(self._btn_edit)
        btn_layout.addWidget(self._btn_remove)
        btn_layout.addStretch()
        inner.addWidget(btn_row)

        return group

    def _build_form_group(self) -> QGroupBox:
        self._form_group = QGroupBox()
        self._form_group.setStyleSheet(GROUP_STYLE)
        inner = QVBoxLayout(self._form_group)
        inner.setContentsMargins(12, 16, 12, 12)
        inner.setSpacing(8)

        name_lbl = QLabel("Name")
        name_lbl.setStyleSheet(LABEL_STYLE)
        self._input_name = QLineEdit()
        self._input_name.setStyleSheet(_INPUT_STYLE)
        self._input_name.setPlaceholderText("e.g. Epoxy 2024")

        desc_lbl = QLabel("Description")
        desc_lbl.setStyleSheet(LABEL_STYLE)
        self._input_desc = QLineEdit()
        self._input_desc.setStyleSheet(_INPUT_STYLE)
        self._input_desc.setPlaceholderText("Optional description")

        inner.addWidget(name_lbl)
        inner.addWidget(self._input_name)
        inner.addWidget(desc_lbl)
        inner.addWidget(self._input_desc)

        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 4, 0, 0)
        btn_layout.setSpacing(8)

        self._btn_save = QPushButton("Save")
        self._btn_save.setStyleSheet(ACTION_BTN_STYLE)
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save.clicked.connect(self._on_save)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setStyleSheet(GHOST_BTN_STYLE)
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.clicked.connect(self._hide_form)

        btn_layout.addWidget(self._btn_save)
        btn_layout.addWidget(self._btn_cancel)
        btn_layout.addStretch()
        inner.addWidget(btn_row)

        return self._form_group

    # ── Table population ───────────────────────────────────────────────────────

    def _refresh_table(self):
        self._table.setRowCount(0)
        for name in self.BUILTIN_TYPES:
            self._add_row(name, "Built-in", builtin=True)
        for gt in self._custom_types:
            self._add_row(gt.name, gt.description, builtin=False)

    def _add_row(self, name: str, description: str, builtin: bool):
        row = self._table.rowCount()
        self._table.insertRow(row)
        for col, text in enumerate([name, description]):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if builtin:
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
                item.setForeground(Qt.GlobalColor.gray)
            self._table.setItem(row, col, item)

    # ── Selection ──────────────────────────────────────────────────────────────

    def _selected_name(self) -> str | None:
        items = self._table.selectedItems()
        return self._table.item(items[0].row(), 0).text() if items else None

    def _on_selection_changed(self):
        print(f"Selection changed: {self._selected_name()}")
        name = self._selected_name()
        is_custom = name is not None and name not in self.BUILTIN_TYPES
        self._btn_edit.setEnabled(is_custom)
        self._btn_remove.setEnabled(is_custom)

    # ── Form show / hide ───────────────────────────────────────────────────────

    def _show_form(self, title: str):
        self._form_group.setTitle(title)
        self._form_group.setVisible(True)
        self._btn_add.setEnabled(False)
        self._btn_edit.setEnabled(False)
        self._btn_remove.setEnabled(False)
        self._input_name.setFocus()

    def _hide_form(self):
        self._form_group.setVisible(False)
        self._editing_id = None
        self._input_name.clear()
        self._input_desc.clear()
        self._btn_add.setEnabled(True)
        self._on_selection_changed()

    # ── Button handlers ────────────────────────────────────────────────────────

    def _start_add(self):
        self._editing_id = None
        self._input_name.clear()
        self._input_desc.clear()
        self._show_form("Add Custom Glue Type")

    def _start_edit(self):
        print(f"Edit: {self._selected_name()}")
        name = self._selected_name()
        gt = next((t for t in self._custom_types if t.name == name), None)
        if gt is None:
            return
        self._editing_id = gt.id
        self._input_name.setText(gt.name)
        self._input_desc.setText(gt.description)
        self._show_form("Edit Custom Glue Type")

    def _on_save(self):
        name = self._input_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Name cannot be empty.")
            return
        description = self._input_desc.text().strip()
        if self._editing_id is None:
            self.add_requested.emit(name, description)
        else:
            self.update_requested.emit(self._editing_id, name, description)
        self._hide_form()

    def _on_remove(self):
        name = self._selected_name()
        gt = next((t for t in self._custom_types if t.name == name), None)
        if gt is None:
            return
        reply = QMessageBox.question(
            self, "Confirm Remove",
            f"Remove '{name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.remove_requested.emit(gt.id)

    # ── Public API ─────────────────────────────────────────────────────────────

    def load_types(self, types: List[GlueType]) -> None:
        """Replace the current custom type list and refresh the table."""
        self._custom_types = list(types)
        self._refresh_table()

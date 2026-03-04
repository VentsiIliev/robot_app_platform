import logging
import qtawesome as qta
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QWidget, QSplitter,
)
from src.applications.base.i_application_view import IApplicationView

_logger = logging.getLogger(__name__)
_ACCENT = "#905BA9"
_HOV    = "#7A4D92"
_BG     = "#ffffff"
_TEXT   = "#111111"
_MUTED  = "#666666"
_BORDER = "#cccccc"

_BTN = f"""
    QPushButton {{
        background: {_ACCENT}; color: white;
        border: none; border-radius: 4px;
        padding: 6px 14px; font-size: 13px;
        min-height: 34px;
    }}
    QPushButton:hover {{ background: {_HOV}; }}
    QPushButton:disabled {{ background: {_BORDER}; color: {_MUTED}; }}
"""
_TABLE = f"""
    QTableWidget {{
        background: {_BG}; color: {_TEXT};
        gridline-color: {_BORDER}; border: 1px solid {_BORDER};
    }}
    QTableWidget::item:selected {{ background: {_ACCENT}; color: white; }}
    QHeaderView::section {{
        background: #f0f0f0; color: {_TEXT};
        border: none; border-bottom: 1px solid {_BORDER};
        padding: 4px; font-weight: bold;
    }}
"""


class ToolSettingsView(IApplicationView):



    add_tool_requested    = pyqtSignal()
    edit_tool_requested   = pyqtSignal(int, str)   # tool_id, name
    remove_tool_requested = pyqtSignal(int)         # tool_id
    update_slot_requested = pyqtSignal(int, int)    # slot_id, tool_id
    add_slot_requested    = pyqtSignal()
    edit_slot_requested   = pyqtSignal(int, object)  # slot_id, current_tool_id (int or None)
    remove_slot_requested = pyqtSignal(int)         # slot_id
    save_slots_requested  = pyqtSignal(list)        # list of (slot_id, tool_id) tuples


    def __init__(self, parent=None):
        super().__init__("ToolSettings", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background: {_BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Tool Changer Configuration")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {_TEXT};")
        root.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_tools_panel())
        splitter.addWidget(self._build_slots_panel())
        splitter.setSizes([500, 500])
        root.addWidget(splitter, stretch=1)

        # Save button spans full width below both panels
        self._btn_save_slots = QPushButton(qta.icon("fa5s.save", color="white"), "  Save All Changes")
        self._btn_save_slots.setStyleSheet(_BTN)
        self._btn_save_slots.setMinimumHeight(44)
        self._btn_save_slots.clicked.connect(self._on_save_slots)
        root.addWidget(self._btn_save_slots)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
        root.addWidget(self._status)

    def _build_tools_panel(self) -> QWidget:
        box = QGroupBox("Tools / Grippers")
        box.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {_TEXT}; }}")
        layout = QVBoxLayout(box)

        self._tools_table = QTableWidget(0, 2)
        self._tools_table.setHorizontalHeaderLabels(["ID", "Name"])
        self._tools_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tools_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._tools_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tools_table.setStyleSheet(_TABLE)
        layout.addWidget(self._tools_table)

        btn_row = QHBoxLayout()
        self._btn_add_tool    = QPushButton(qta.icon("fa5s.plus",   color="white"), "  Add")
        self._btn_edit_tool   = QPushButton(qta.icon("fa5s.pen",    color="white"), "  Edit")
        self._btn_remove_tool = QPushButton(qta.icon("fa5s.trash",  color="white"), "  Remove")
        for b in (self._btn_add_tool, self._btn_edit_tool, self._btn_remove_tool):
            b.setStyleSheet(_BTN)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self._btn_add_tool.clicked.connect(self.add_tool_requested.emit)
        self._btn_edit_tool.clicked.connect(self._on_edit_tool)
        self._btn_remove_tool.clicked.connect(self._on_remove_tool)
        self._tools_table.itemSelectionChanged.connect(self._on_tool_selection)
        self._btn_edit_tool.setEnabled(False)
        self._btn_remove_tool.setEnabled(False)

        return box

    def _build_slots_panel(self) -> QWidget:
        from PyQt6.QtWidgets import QComboBox
        box = QGroupBox("Slot ↔ Tool Assignments")
        box.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {_TEXT}; }}")
        layout = QVBoxLayout(box)

        self._slots_table = QTableWidget(0, 2)
        self._slots_table.setHorizontalHeaderLabels(["Slot ID", "Assigned Tool"])
        self._slots_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._slots_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._slots_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._slots_table.setStyleSheet(_TABLE)
        self._slots_table.itemSelectionChanged.connect(self._on_slot_selection)
        layout.addWidget(self._slots_table)

        btn_row = QHBoxLayout()
        self._btn_add_slot = QPushButton(qta.icon("fa5s.plus", color="white"), "  Add Slot")
        self._btn_edit_slot = QPushButton(qta.icon("fa5s.pen", color="white"), "  Edit Slot")
        self._btn_remove_slot = QPushButton(qta.icon("fa5s.trash", color="white"), "  Remove Slot")
        for b in (self._btn_add_slot, self._btn_edit_slot, self._btn_remove_slot):
            b.setStyleSheet(_BTN)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self._btn_add_slot.clicked.connect(self.add_slot_requested.emit)
        self._btn_edit_slot.clicked.connect(self._on_edit_slot)
        self._btn_remove_slot.clicked.connect(self._on_remove_slot)
        self._btn_edit_slot.setEnabled(False)
        self._btn_remove_slot.setEnabled(False)

        return box

    # ── Setters ──────────────────────────────────────────────────────

    def set_tools(self, tools) -> None:
        self._tools_table.setRowCount(0)
        for t in tools:
            row = self._tools_table.rowCount()
            self._tools_table.insertRow(row)
            self._tools_table.setItem(row, 0, QTableWidgetItem(str(t.id)))
            self._tools_table.setItem(row, 1, QTableWidgetItem(t.name))

    def set_slots(self, slots, tools) -> None:
        from PyQt6.QtWidgets import QComboBox
        self._slots_table.setRowCount(0)
        for s in slots:
            row = self._slots_table.rowCount()
            self._slots_table.insertRow(row)
            self._slots_table.setItem(row, 0, QTableWidgetItem(str(s.id)))
            combo = QComboBox()
            combo.setStyleSheet(f"border: 1px solid {_ACCENT};")
            combo.addItem("— Unassigned —", None)
            for t in tools:
                combo.addItem(f"{t.name} ({t.id})", t.id)
            idx = combo.findData(s.tool_id)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            self._slots_table.setCellWidget(row, 1, combo)

    def set_status(self, msg: str) -> None:
        self._status.setText(msg)

    def selected_tool(self):
        rows = self._tools_table.selectedItems()
        if not rows:
            return None, None
        row = self._tools_table.currentRow()
        return (
            int(self._tools_table.item(row, 0).text()),
            self._tools_table.item(row, 1).text(),
        )

    # ── Slots ────────────────────────────────────────────────────────

    def _on_tool_selection(self) -> None:
        has = bool(self._tools_table.selectedItems())
        self._btn_edit_tool.setEnabled(has)
        self._btn_remove_tool.setEnabled(has)

    def _on_edit_tool(self) -> None:
        tid, name = self.selected_tool()
        if tid is not None:
            self.edit_tool_requested.emit(tid, name)

    def _on_remove_tool(self) -> None:
        tid, _ = self.selected_tool()
        if tid is not None:
            self.remove_tool_requested.emit(tid)

    def _on_save_slot(self) -> None:
        from PyQt6.QtWidgets import QComboBox
        for row in range(self._slots_table.rowCount()):
            slot_id = int(self._slots_table.item(row, 0).text())
            combo   = self._slots_table.cellWidget(row, 1)
            if isinstance(combo, QComboBox):
                tool_id = combo.currentData()
                self.update_slot_requested.emit(slot_id, tool_id)

    def selected_slot_id(self):
        rows = self._slots_table.selectedItems()
        if not rows:
            return None
        row = self._slots_table.currentRow()
        return int(self._slots_table.item(row, 0).text())

    def selected_slot(self):
        if not self._slots_table.selectedItems():
            return None, None
        from PyQt6.QtWidgets import QComboBox
        row = self._slots_table.currentRow()
        sid = int(self._slots_table.item(row, 0).text())
        combo = self._slots_table.cellWidget(row, 1)
        tid = combo.currentData() if isinstance(combo, QComboBox) else None
        return sid, tid

    def selected_slot_id(self):
        sid, _ = self.selected_slot()
        return sid

    def _on_slot_selection(self) -> None:
        has = bool(self._slots_table.selectedItems())
        self._btn_edit_slot.setEnabled(has)
        self._btn_remove_slot.setEnabled(has)

    def _on_edit_slot(self) -> None:
        sid, tid = self.selected_slot()
        if sid is not None and tid is not None:
            self.edit_slot_requested.emit(sid, tid)

    def _on_remove_slot(self) -> None:
        sid = self.selected_slot_id()
        if sid is not None:
            self.remove_slot_requested.emit(sid)

    def _on_save_slots(self) -> None:
        from PyQt6.QtWidgets import QComboBox
        result = []
        for row in range(self._slots_table.rowCount()):
            slot_id = int(self._slots_table.item(row, 0).text())
            combo   = self._slots_table.cellWidget(row, 1)
            if isinstance(combo, QComboBox):
                tool_id = combo.currentData()   # None for Unassigned
                result.append((slot_id, tool_id))
        self.save_slots_requested.emit(result)

    def clean_up(self) -> None:
        pass
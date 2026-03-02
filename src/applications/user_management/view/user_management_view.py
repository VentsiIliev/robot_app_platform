from typing import List, Optional
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QSizePolicy, QWidget, QLineEdit, QPushButton,
)
from PyQt6.QtGui import QFont

from src.applications.base.i_application_view import IApplicationView
from src.applications.user_management.domain.user_schema import UserRecord, UserSchema


class UserManagementView(IApplicationView):

    add_requested     = pyqtSignal()
    edit_requested    = pyqtSignal(object)    # UserRecord
    delete_requested  = pyqtSignal(object)    # UserRecord
    qr_requested      = pyqtSignal(object)    # UserRecord
    refresh_requested = pyqtSignal()
    filter_changed    = pyqtSignal(str, str)  # column label, value

    def __init__(self, schema: UserSchema, parent=None):
        self._schema = schema
        super().__init__("User Management", parent)

    # ── IApplicationView ─────────────────────────────────────────────

    def setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("User Management")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont(); f.setPointSize(16); f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        root.addWidget(self._build_filter_bar())
        root.addWidget(self._build_table())
        root.addWidget(self._build_buttons())

        self._status = QLabel()
        root.addWidget(self._status)
        self.setStyleSheet(self._stylesheet())

    def clean_up(self) -> None:
        pass

    # ── Public setters ────────────────────────────────────────────────

    def set_users(self, records: List[UserRecord]) -> None:
        table_fields = self._schema.get_table_fields()
        self._table.clearContents()
        self._table.setRowCount(len(records))
        for row, record in enumerate(records):
            for col, fd in enumerate(table_fields):
                val  = record.get(fd.key, "")
                text = "****" if fd.mask_in_table and val else str(val)
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, record)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self._table.setItem(row, col, item)
        self._table.viewport().update()

    def set_status(self, msg: str) -> None:
        self._status.setText(msg)

    def selected_record(self) -> Optional[UserRecord]:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ── Builders ─────────────────────────────────────────────────────

    def _build_filter_bar(self) -> QWidget:
        group  = QGroupBox("Filter")
        layout = QHBoxLayout(group)
        layout.addWidget(QLabel("Filter by:"))

        self._filter_col = QComboBox()
        self._filter_col.addItems(self._schema.get_filterable_labels())
        layout.addWidget(self._filter_col)

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Enter filter value…")
        layout.addWidget(self._filter_input)

        btn_apply = QPushButton("Filter")
        btn_clear = QPushButton("Clear")
        btn_apply.clicked.connect(self._emit_filter)
        btn_clear.clicked.connect(self._clear_filter)
        self._filter_input.returnPressed.connect(self._emit_filter)
        layout.addWidget(btn_apply)
        layout.addWidget(btn_clear)
        return group

    def _build_table(self) -> QTableWidget:
        self._table = QTableWidget()
        self._table.setColumnCount(len(self._schema.get_table_fields()))
        self._table.setHorizontalHeaderLabels(self._schema.get_table_headers())
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setMinimumHeight(200)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        return self._table

    def _build_buttons(self) -> QWidget:
        group  = QGroupBox()
        layout = QHBoxLayout(group)

        self._btn_add     = QPushButton("Add User")
        self._btn_edit    = QPushButton("Edit User")
        self._btn_delete  = QPushButton("Delete User")
        self._btn_refresh = QPushButton("Refresh")
        self._btn_qr      = QPushButton("Generate QR")

        for btn in (self._btn_add, self._btn_edit, self._btn_delete, self._btn_refresh, self._btn_qr):
            btn.setMinimumHeight(48)
            layout.addWidget(btn)

        self._btn_edit.setEnabled(False)
        self._btn_delete.setEnabled(False)
        self._btn_qr.setEnabled(False)

        self._btn_add.clicked.connect(self._on_add)
        self._btn_edit.clicked.connect(self._on_edit)
        self._btn_delete.clicked.connect(self._on_delete)
        self._btn_refresh.clicked.connect(self.refresh_requested)
        self._btn_qr.clicked.connect(self._on_qr)
        return group

    # ── Internal slots ────────────────────────────────────────────────

    def _on_selection_changed(self) -> None:
        has = self.selected_record() is not None
        self._btn_edit.setEnabled(has)
        self._btn_delete.setEnabled(has)
        self._btn_qr.setEnabled(has)

    def _on_add(self)    -> None: self.add_requested.emit()
    def _on_edit(self)   -> None:
        r = self.selected_record()
        if r: self.edit_requested.emit(r)
    def _on_delete(self) -> None:
        r = self.selected_record()
        if r: self.delete_requested.emit(r)
    def _on_qr(self)     -> None:
        r = self.selected_record()
        if r: self.qr_requested.emit(r)

    def _emit_filter(self) -> None:
        self.filter_changed.emit(self._filter_col.currentText(), self._filter_input.text().strip())

    def _clear_filter(self) -> None:
        self._filter_input.clear()
        self._filter_col.setCurrentIndex(0)
        self.filter_changed.emit("All", "")

    @staticmethod
    def _stylesheet() -> str:
        return """
            QWidget { background-color: white; color: black; }
            QHeaderView::section { background-color: #f0f0f0; color: black; padding: 4px; border: 1px solid #d0d0d0; }
            QGroupBox { font-weight: bold; border: 2px solid #cccccc; border-radius: 5px; margin-top: 1ex; padding-top: 10px; }
            QTableWidget { gridline-color: #d0d0d0; background-color: white; alternate-background-color: #f5f5f5; color: black; }
            QTableWidget::item:selected { background-color: #905BA9; color: white; }
            QPushButton { background-color: #905BA9; border: none; color: white; padding: 8px 16px; font-size: 14px; border-radius: 4px; }
            QPushButton:hover { background-color: #7A4D92; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """

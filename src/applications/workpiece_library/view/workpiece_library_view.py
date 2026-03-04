import logging
from typing import List, Optional

import qtawesome as qta
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QSizePolicy, QWidget,
    QFrame, QScrollArea, QSplitter,
)
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QSizePolicy, QWidget,
    QFrame, QScrollArea, QSplitter, QComboBox,    # ← add QComboBox
)


from src.applications.base.i_application_view import IApplicationView
from src.applications.workpiece_library.domain.workpiece_schema import WorkpieceSchema, WorkpieceRecord

_logger = logging.getLogger(__name__)

_ACCENT     = "#905BA9"
_ACCENT_HOV = "#7A4D92"
_BG         = "#ffffff"
_BG_ALT     = "#f5f5f5"
_BORDER     = "#cccccc"
_TEXT       = "#111111"
_MUTED      = "#666666"


class WorkpieceLibraryView(IApplicationView):

    delete_requested  = pyqtSignal(str)   # workpiece_id
    refresh_requested = pyqtSignal()
    search_changed    = pyqtSignal(str)
    selection_changed = pyqtSignal(object)  # WorkpieceRecord | None
    edit_requested = pyqtSignal(object, dict)  # record, {key: new_value}
    open_in_editor_requested = pyqtSignal(object)  # WorkpieceRecord

    def __init__(self, schema: WorkpieceSchema, parent=None):
        self._schema = schema
        self._edit_widgets: dict = {}
        super().__init__("Workpiece Library", parent)

    # ── IApplicationView ─────────────────────────────────────────────

    def setup_ui(self) -> None:
        self.setStyleSheet(self._stylesheet())
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        root.addWidget(self._build_header())
        root.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_list_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, stretch=1)

        root.addWidget(self._build_action_bar())

        self._status = QLabel()
        self._status.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
        root.addWidget(self._status)

    def clean_up(self) -> None:
        pass

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_requested.emit()
    # ── Public setters ────────────────────────────────────────────────

    def set_records(self, records: List[WorkpieceRecord]) -> None:
        fields = self._schema.get_table_fields()
        self._table.setSortingEnabled(False)
        self._table.clearContents()
        self._table.setRowCount(len(records))
        for row, record in enumerate(records):
            for col, fd in enumerate(fields):
                item = QTableWidgetItem(str(record.get(fd.key, "")))
                item.setData(Qt.ItemDataRole.UserRole, record)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self._table.setItem(row, col, item)
        self._table.setSortingEnabled(True)
        self._table.viewport().update()

    def set_detail(self, record: Optional[WorkpieceRecord]) -> None:
        while self._detail_layout.count():
            child = self._detail_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._edit_widgets: dict = {}  # key → QLineEdit (editable fields only)

        if record is None:
            placeholder = QLabel("Select a workpiece to view details")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(f"color: {_MUTED};")
            self._detail_layout.addWidget(placeholder)
            self._btn_delete.setEnabled(False)
            self._btn_save.setEnabled(False)
            return

        for fd in self._schema.get_detail_fields():
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 2, 4, 2)

            lbl_key = QLabel(f"{fd.label}:")
            lbl_key.setFixedWidth(120)
            lbl_key.setStyleSheet(f"font-weight: bold; color: {_TEXT};")
            row_layout.addWidget(lbl_key)

            if fd.editable:
                if fd.widget == "combo" and fd.options:
                    combo = QComboBox()
                    for opt in fd.options:
                        combo.addItem(str(opt))
                    current = str(record.get(fd.key, ""))
                    idx = combo.findText(current)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    combo.setStyleSheet(
                        f"border: 1px solid {_ACCENT}; border-radius: 4px; padding: 2px 6px;"
                    )
                    row_layout.addWidget(combo, stretch=1)
                    self._edit_widgets[fd.key] = combo
                else:
                    edit = QLineEdit(str(record.get(fd.key, "")))
                    edit.setStyleSheet(
                        f"border: 1px solid {_ACCENT}; border-radius: 4px; padding: 2px 6px;"
                    )
                    row_layout.addWidget(edit, stretch=1)
                    self._edit_widgets[fd.key] = edit
            else:
                lbl_val = QLabel(str(record.get(fd.key, "—")))
                lbl_val.setWordWrap(True)
                lbl_val.setStyleSheet(f"color: {_TEXT};")
                row_layout.addWidget(lbl_val, stretch=1)

            self._detail_layout.addWidget(row_widget)

        self._detail_layout.addStretch()
        self._btn_open.setEnabled(record is not None)
        self._btn_delete.setEnabled(True)
        self._btn_save.setEnabled(bool(self._edit_widgets))


    def set_thumbnail(self, image_bytes: Optional[bytes]) -> None:
        if image_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(image_bytes)
            self._thumbnail.setPixmap(
                pixmap.scaled(220, 160,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self._thumbnail.setPixmap(QPixmap())
            self._thumbnail.setText("No preview")

    def set_status(self, msg: str) -> None:
        self._status.setText(msg)

    def selected_record(self) -> Optional[WorkpieceRecord]:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ── Builders ─────────────────────────────────────────────────────

    def _build_header(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 4)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            qta.icon("fa5s.archive", color=_ACCENT).pixmap(QSize(28, 28))
        )
        layout.addWidget(icon_lbl)

        title = QLabel("Workpiece Library")
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        title.setFont(f)
        title.setStyleSheet(f"color: {_TEXT};")
        layout.addWidget(title)
        layout.addStretch()
        return w

    def _build_toolbar(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        search_icon = QLabel()
        search_icon.setPixmap(qta.icon("fa5s.search", color=_MUTED).pixmap(QSize(16, 16)))
        layout.addWidget(search_icon)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by name or ID…")
        self._search.setMinimumHeight(36)
        self._search.textChanged.connect(self.search_changed)
        layout.addWidget(self._search, stretch=1)

        btn_refresh = QPushButton()
        btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="white"))
        btn_refresh.setToolTip("Refresh")
        btn_refresh.setFixedSize(36, 36)
        btn_refresh.clicked.connect(self.refresh_requested)
        layout.addWidget(btn_refresh)
        return w

    def _build_list_panel(self) -> QWidget:
        group = QGroupBox("Workpieces")
        layout = QVBoxLayout(group)

        fields = self._schema.get_table_fields()
        self._table = QTableWidget()
        self._table.setColumnCount(len(fields))
        self._table.setHorizontalHeaderLabels(self._schema.get_table_headers())
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.setMinimumHeight(300)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self._table)
        return group

    def _build_detail_panel(self) -> QWidget:
        group = QGroupBox("Details")
        outer = QVBoxLayout(group)

        # thumbnail
        self._thumbnail = QLabel("No preview")
        self._thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail.setFixedHeight(160)
        self._thumbnail.setStyleSheet(
            f"background: {_BG_ALT}; border: 1px solid {_BORDER}; color: {_MUTED};"
        )
        outer.addWidget(self._thumbnail)

        # scrollable field list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self._detail_layout = QVBoxLayout(container)
        self._detail_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._detail_layout.setSpacing(4)

        placeholder = QLabel("Select a workpiece to view details")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(f"color: {_MUTED};")
        self._detail_layout.addWidget(placeholder)

        scroll.setWidget(container)
        outer.addWidget(scroll, stretch=1)
        return group

    def _build_action_bar(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)
        layout.addStretch()

        self._btn_save = QPushButton(
            qta.icon("fa5s.save", color="white"), "  Save"
        )
        self._btn_save.setMinimumHeight(44)
        self._btn_save.setMinimumWidth(140)
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)

        self._btn_delete = QPushButton(
            qta.icon("fa5s.trash-alt", color="white"), "  Delete"
        )
        self._btn_delete.setMinimumHeight(44)
        self._btn_delete.setMinimumWidth(140)
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._on_delete)

        self._btn_open = QPushButton(
            qta.icon("fa5s.external-link-alt", color="white"), "  Open in Editor"
        )

        self._btn_open.setMinimumHeight(44)
        self._btn_open.setMinimumWidth(160)
        self._btn_open.setEnabled(False)
        self._btn_open.clicked.connect(self._on_open_in_editor)

        layout.addWidget(self._btn_open)
        layout.addWidget(self._btn_save)
        layout.addWidget(self._btn_delete)
        return w

    # ── Internal slots ────────────────────────────────────────────────

    def _on_open_in_editor(self) -> None:
        record = self.selected_record()
        if record:
            self.open_in_editor_requested.emit(record)

    def _on_selection_changed(self) -> None:
        record = self.selected_record()
        self.set_detail(record)
        self.selection_changed.emit(record)

    def _on_delete(self) -> None:
        record = self.selected_record()
        if record:
            self.delete_requested.emit(
                str(record.get_id(self._schema.id_key))
            )

    def _on_save(self) -> None:
        record = self.selected_record()
        if record and hasattr(self, "_edit_widgets"):
            updates = {}
            for key, widget in self._edit_widgets.items():
                if hasattr(widget, "currentText"):
                    updates[key] = widget.currentText()
                else:
                    updates[key] = widget.text()
            self.edit_requested.emit(record, updates)

    # ── Stylesheet ────────────────────────────────────────────────────

    @staticmethod
    def _stylesheet() -> str:
        return f"""
            QWidget {{ background-color: {_BG}; color: {_TEXT}; }}
            QGroupBox {{
                font-weight: bold; font-size: 13px;
                border: 2px solid {_BORDER}; border-radius: 6px;
                margin-top: 1ex; padding-top: 10px;
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
            QTableWidget {{
                gridline-color: #d0d0d0; background-color: {_BG};
                alternate-background-color: {_BG_ALT}; color: {_TEXT};
            }}
            QTableWidget::item:selected {{ background-color: {_ACCENT}; color: white; }}
            QHeaderView::section {{
                background-color: #f0f0f0; color: {_TEXT};
                padding: 4px; border: 1px solid #d0d0d0; font-weight: bold;
            }}
            QLineEdit {{
                border: 1px solid {_BORDER}; border-radius: 4px;
                padding: 4px 8px; background: white; color: {_TEXT};
            }}
            QLineEdit:focus {{ border-color: {_ACCENT}; }}
            QPushButton {{
                background-color: {_ACCENT}; border: none; color: white;
                padding: 8px 16px; font-size: 13px; border-radius: 4px;
            }}
            QPushButton:hover  {{ background-color: {_ACCENT_HOV}; }}
            QPushButton:disabled {{ background-color: #cccccc; color: #888888; }}
            QScrollArea {{ border: none; background: transparent; }}
        """
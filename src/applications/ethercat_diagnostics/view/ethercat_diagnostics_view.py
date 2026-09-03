from __future__ import annotations

import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    BORDER,
    GHOST_BTN_STYLE,
    LABEL_STYLE,
    PRIMARY,
    TEXT_COLOR,
)
from src.applications.base.app_styles import APP_PANEL_BG, muted_text_style, table_style
from src.applications.base.i_application_view import IApplicationView
from src.applications.ethercat_diagnostics.service.i_ethercat_diagnostics_service import (
    EthercatDiagnosticsSnapshot,
)


class EthercatDiagnosticsView(IApplicationView):
    refresh_requested = pyqtSignal()
    reset_errors_requested = pyqtSignal()

    def __init__(self) -> None:
        self._refresh_btn = None
        self._reset_btn = None
        self._status_value = None
        self._message = None
        self._table = None
        self._raw = None
        super().__init__("EtherCAT Diagnostics")

    def setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        self.setStyleSheet(f"background-color: {BG_COLOR};")

        header = QHBoxLayout()
        title = QLabel(self.tr("EtherCAT Diagnostics"))
        title.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 18pt; font-weight: bold; background: transparent;")
        header.addWidget(title)
        header.addStretch(1)

        self._refresh_btn = QPushButton(self.tr("Refresh"))
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        header.addWidget(self._refresh_btn)

        self._reset_btn = QPushButton(self.tr("Reset Errors"))
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._reset_btn.clicked.connect(self.reset_errors_requested.emit)
        header.addWidget(self._reset_btn)
        root.addLayout(header)

        summary = QWidget()
        summary.setStyleSheet(f"background: {APP_PANEL_BG}; border: 1px solid {BORDER}; border-radius: 6px;")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(14, 10, 14, 10)
        summary_layout.setSpacing(12)

        state_label = QLabel(self.tr("Master State"))
        state_label.setStyleSheet(LABEL_STYLE)
        summary_layout.addWidget(state_label)

        self._status_value = QLabel(self.tr("UNKNOWN"))
        self._status_value.setMinimumWidth(150)
        self._status_value.setStyleSheet(f"color: {PRIMARY}; font-size: 13pt; font-weight: bold; background: transparent;")
        summary_layout.addWidget(self._status_value)

        self._message = QLabel("")
        self._message.setWordWrap(True)
        self._message.setStyleSheet(muted_text_style())
        summary_layout.addWidget(self._message, 1)
        root.addWidget(summary)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels([
            self.tr("ID"),
            self.tr("Name"),
            self.tr("State"),
            self.tr("Online"),
            self.tr("Operational"),
            self.tr("Error"),
            self.tr("Statusword"),
            self.tr("Details"),
        ])
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setStyleSheet(table_style(radius=6))
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self._table, 2)

        raw_label = QLabel(self.tr("Raw Provider Payload"))
        raw_label.setStyleSheet(LABEL_STYLE)
        root.addWidget(raw_label)

        self._raw = QTextEdit()
        self._raw.setReadOnly(True)
        self._raw.setMinimumHeight(160)
        self._raw.setStyleSheet(f"""
QTextEdit {{
    background: {APP_PANEL_BG};
    color: {TEXT_COLOR};
    border: 1px solid {BORDER};
    border-radius: 6px;
    font-family: monospace;
    font-size: 9pt;
}}
""")
        root.addWidget(self._raw, 1)

    def clean_up(self) -> None:
        return None

    def set_busy(self, busy: bool) -> None:
        if self._refresh_btn is not None:
            self._refresh_btn.setEnabled(not busy)
        if self._reset_btn is not None:
            self._reset_btn.setEnabled((not busy) and self._reset_btn.property("supported") is True)

    def set_reset_enabled(self, enabled: bool) -> None:
        if self._reset_btn is not None:
            self._reset_btn.setProperty("supported", bool(enabled))
            self._reset_btn.setEnabled(bool(enabled))

    def set_status_message(self, message: str, *, ok: bool) -> None:
        if self._message is not None:
            prefix = self.tr("OK") if ok else self.tr("ERROR")
            self._message.setText(f"{prefix}: {message}")

    def set_snapshot(self, snapshot: EthercatDiagnosticsSnapshot) -> None:
        self._status_value.setText(str(snapshot.master_state or "unknown").upper())
        self._message.setText(str(snapshot.master_message or ""))
        self._set_slave_rows(snapshot)
        self._raw.setPlainText(json.dumps(snapshot.raw, indent=2, sort_keys=True, default=str))

    def _set_slave_rows(self, snapshot: EthercatDiagnosticsSnapshot) -> None:
        self._table.setRowCount(len(snapshot.slaves))
        for row, slave in enumerate(snapshot.slaves):
            values = [
                slave.slave_id,
                slave.name,
                slave.state,
                self._bool_text(slave.online),
                self._bool_text(slave.operational),
                slave.error,
                self._statusword_text(slave.statusword),
                json.dumps(slave.details, sort_keys=True, default=str) if slave.details else "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col in {0, 3, 4, 6} else Qt.AlignmentFlag.AlignLeft)
                self._table.setItem(row, col, item)

    @staticmethod
    def _bool_text(value: bool | None) -> str:
        if value is True:
            return "YES"
        if value is False:
            return "NO"
        return ""

    @staticmethod
    def _statusword_text(value) -> str:
        if isinstance(value, int):
            return f"0x{value:04X}"
        return "" if value is None else str(value)

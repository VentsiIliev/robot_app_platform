from PyQt6.QtCore import pyqtSignal, Qt, QEvent, QCoreApplication
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QCheckBox, QHeaderView, QWidget,
)
from PyQt6.QtGui import QFont


class PermissionsView(QWidget):
    """App Permissions tab — checkbox table of app_id × role_value.

    Signals:
        permission_toggled(app_id, role_value, allowed)
    """

    permission_toggled = pyqtSignal(str, str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self._build_ui()

    # ── public API (called by PermissionsController) ───────────────────────────

    def set_permissions(
        self,
        app_ids:     list[str],
        role_values: list[str],
        permissions: dict[str, list[str]],
    ) -> None:
        """Populate the table. Suppresses checkbox signals during population."""
        self._loading = True
        try:
            self._table.setRowCount(len(app_ids))
            self._table.setColumnCount(len(role_values))
            self._table.setHorizontalHeaderLabels([self._t(r) for r in role_values])
            self._table.setVerticalHeaderLabels(app_ids)

            for row, app_id in enumerate(app_ids):
                allowed = permissions.get(app_id, ["Admin"])
                for col, role_value in enumerate(role_values):
                    cell   = QWidget()
                    layout = QHBoxLayout(cell)
                    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    layout.setContentsMargins(0, 0, 0, 0)
                    cb = QCheckBox()
                    cb.setChecked(role_value in allowed)
                    cb.stateChanged.connect(
                        self._make_toggle_handler(app_id, role_value, cb)
                    )
                    layout.addWidget(cb)
                    self._table.setCellWidget(row, col, cell)
        finally:
            self._loading = False

    def set_notice(self, text: str) -> None:
        self._notice.setText(text)

    # ── Localization ───────────────────────────────────────────────────────────

    @staticmethod
    def _t(text: str) -> str:
        translated = QCoreApplication.translate("UserManagement", text)
        return translated or text

    def retranslateUi(self, *_) -> None:
        self._title_label.setText(self._t("App Permissions"))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self._title_label = QLabel()
        f = QFont(); f.setPointSize(14); f.setBold(True)
        self._title_label.setFont(f)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._title_label)

        self._table = QTableWidget()
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self._table)

        self._notice = QLabel()
        self._notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._notice.setStyleSheet("color: gray; font-style: italic;")
        root.addWidget(self._notice)

        self.retranslateUi()

    def _make_toggle_handler(self, app_id: str, role_value: str, cb: QCheckBox):
        def _on_state_changed(_state):
            if not self._loading:
                self.permission_toggled.emit(app_id, role_value, cb.isChecked())
        return _on_state_changed

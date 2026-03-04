import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QVBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from src.applications.base.i_application_controller import IApplicationController
from src.applications.user_management.domain.user_schema import UserRecord, UserSchema, FieldDescriptor
from src.applications.user_management.model.user_management_model import UserManagementModel
from src.applications.user_management.view.user_management_view import UserManagementView
from src.applications.base.styled_message_box import show_warning, show_info, ask_yes_no

_logger = logging.getLogger(__name__)


class UserManagementController(IApplicationController):

    def __init__(self, model: UserManagementModel, view: UserManagementView):
        self._model = model
        self._view  = view

    def load(self) -> None:
        self._connect_signals()
        self._refresh()

    def stop(self) -> None:
        pass

    def _connect_signals(self) -> None:
        self._view.add_requested.connect(self._on_add)
        self._view.edit_requested.connect(self._on_edit)
        self._view.delete_requested.connect(self._on_delete)
        self._view.qr_requested.connect(self._on_qr)
        self._view.refresh_requested.connect(self._refresh)
        self._view.filter_changed.connect(self._on_filter)

    def _refresh(self) -> None:
        records = self._model.load()
        self._view.set_users(records)
        self._view.set_status(f"{len(records)} users loaded")

    def _on_add(self) -> None:
        dialog = _UserDialog(schema=self._model.schema, parent=self._view)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                record = dialog.get_record()
                ok, msg = self._model.add_user(record)
                self._view.set_status(msg)
                if ok:
                    self._view.set_users(self._model.get_users())
                else:
                    show_warning(self._view, "Add User", msg)
            except ValueError as exc:
                show_warning(self._view, "Invalid Input", str(exc))

    def _on_edit(self, record: UserRecord) -> None:
        dialog = _UserDialog(schema=self._model.schema, record=record, parent=self._view)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                updated = dialog.get_record()
                ok, msg = self._model.update_user(updated)
                self._view.set_status(msg)
                if ok:
                    self._view.set_users(self._model.get_users())
                else:
                    show_warning(self._view, "Update User", msg)
            except ValueError as exc:
                show_warning(self._view, "Invalid Input", str(exc))

    def _on_delete(self, record: UserRecord) -> None:
        uid = record.get_id(self._model.schema.id_key)
        if not ask_yes_no(self._view, "Confirm Delete", f"Delete user '{uid}'?"):
            return
        ok, msg = self._model.delete_user(uid)
        self._view.set_status(msg)
        if ok:
            self._view.set_users(self._model.get_users())

    def _on_qr(self, record: UserRecord) -> None:
        ok, msg, qr_path = self._model.generate_qr(record)
        if not ok:
            show_warning(self._view, "QR Error", msg)
            return
        _QrDialog(record=record, qr_path=qr_path, model=self._model, parent=self._view).exec()

    def _on_filter(self, column_label: str, value: str) -> None:
        all_records = self._model.get_users()
        if not value or column_label == "All":
            self._view.set_users(all_records)
            self._view.set_status(f"{len(all_records)} users")
            return
        fd = next(
            (f for f in self._model.schema.fields if f.label == column_label and not f.mask_in_table),
            None,
        )
        if fd is None:
            self._view.set_users(all_records)
            return
        filtered = [r for r in all_records if value.lower() in str(r.get(fd.key, "")).lower()]
        self._view.set_users(filtered)
        self._view.set_status(f"{len(filtered)} of {len(all_records)} users")


# ── Schema-driven add/edit dialog ─────────────────────────────────────────────

class _UserDialog(QDialog):

    def __init__(self, schema: UserSchema, parent=None, record: Optional[UserRecord] = None):
        super().__init__(parent)
        self._schema  = schema
        self._record  = record
        self._widgets = {}
        self.setWindowTitle("Edit User" if record else "Add User")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._build_ui()
        if record:
            self._populate(record)

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        for fd in self._schema.fields:
            widget = self._make_widget(fd)
            self._widgets[fd.key] = widget
            layout.addRow(f"{fd.label}:", widget)
        btns       = QHBoxLayout()
        btn_save   = QPushButton("Save");   btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_save); btns.addWidget(btn_cancel)
        layout.addRow(btns)

    @staticmethod
    def _make_widget(fd: FieldDescriptor):
        if fd.widget == "combo" and fd.options:
            w = QComboBox()
            w.addItems(fd.options)
            return w
        w = QLineEdit()
        if fd.widget == "password":
            w.setEchoMode(QLineEdit.EchoMode.Password)
        if fd.widget == "email":
            w.setPlaceholderText("user@example.com")
        return w

    def _populate(self, record: UserRecord) -> None:
        for fd in self._schema.fields:
            w   = self._widgets.get(fd.key)
            val = str(record.get(fd.key, ""))
            if isinstance(w, QComboBox):
                idx = w.findText(val)
                if idx >= 0:
                    w.setCurrentIndex(idx)
            elif isinstance(w, QLineEdit):
                w.setText(val)
                if fd.read_only_on_edit:
                    w.setReadOnly(True)

    def get_record(self) -> UserRecord:
        data = {}
        for fd in self._schema.fields:
            w = self._widgets.get(fd.key)
            if isinstance(w, QComboBox):
                val = w.currentText()
            else:
                val = w.text().strip() if w else ""
            if fd.required and not val:
                raise ValueError(f"'{fd.label}' is required")
            data[fd.key] = val
        return UserRecord(data)


# ── QR dialog ─────────────────────────────────────────────────────────────────

class _QrDialog(QDialog):

    def __init__(self, record: UserRecord, qr_path: Optional[str],
                 model: UserManagementModel, parent=None):
        super().__init__(parent)
        self._record  = record
        self._qr_path = qr_path
        self._model   = model
        uid = record.get_id(model.schema.id_key)
        self.setWindowTitle(f"QR Code — {uid}")
        self.setFixedSize(400, 460)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        if self._qr_path:
            lbl = QLabel()
            lbl.setPixmap(QPixmap(self._qr_path))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
        uid  = self._record.get_id(self._model.schema.id_key)
        info = QLabel(f"ID: {uid}")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)
        btn_email = QPushButton("📧 Email Access Package")
        btn_email.setMinimumHeight(44)
        btn_email.clicked.connect(self._on_send)
        layout.addWidget(btn_email)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _on_send(self) -> None:
        if not self._qr_path:
            return
        ok, msg = self._model.send_access_package(self._record, self._qr_path)
        if ok:
            show_info(self, "Sent", msg)
        else:
            show_warning(self, "Email Error", msg)

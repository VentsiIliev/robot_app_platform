from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QStackedWidget, QWidget, QFormLayout,
)

from src.engine.auth.i_authenticated_user import IAuthenticatedUser


class LoginView(QDialog):
    """Login dialog — two pages: normal login and first-run admin setup."""

    login_submitted      = pyqtSignal(str, str)   # user_id, password
    qr_login_requested   = pyqtSignal(str)         # qr_payload (unused until scanner)
    first_admin_submitted = pyqtSignal(str, str, str, str)  # id, first, last, pw

    _PAGE_LOGIN     = 0
    _PAGE_FIRST_RUN = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setMinimumWidth(420)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self._result_user: Optional[IAuthenticatedUser] = None
        self._setup_ui()
        self.setStyleSheet(self._stylesheet())

    # ── IApplicationView-compatible API ──────────────────────────────────────

    def show_login(self) -> None:
        self._stack.setCurrentIndex(self._PAGE_LOGIN)

    def show_first_run(self) -> None:
        self._stack.setCurrentIndex(self._PAGE_FIRST_RUN)

    def show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def accept_login(self, user: IAuthenticatedUser) -> None:
        self._result_user = user
        self._error_label.setVisible(False)
        self.accept()   # closes dialog with Accepted result

    def result_user(self) -> Optional[IAuthenticatedUser]:
        return self._result_user

    # ── UI construction ──────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("Robot Platform")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont(); f.setPointSize(18); f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_login_page())
        self._stack.addWidget(self._build_first_run_page())
        root.addWidget(self._stack)

        self._error_label = QLabel()
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setStyleSheet("color: red; font-weight: bold;")
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

    def _build_login_page(self) -> QWidget:
        page   = QWidget()
        layout = QFormLayout(page)
        layout.setSpacing(12)

        self._uid_input = QLineEdit()
        self._uid_input.setPlaceholderText("Numeric user ID")
        layout.addRow("User ID:", self._uid_input)

        self._pw_input = QLineEdit()
        self._pw_input.setPlaceholderText("Password")
        self._pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Password:", self._pw_input)

        btn_login = QPushButton("Login")
        btn_login.setMinimumHeight(44)
        btn_login.clicked.connect(self._on_login_clicked)
        self._pw_input.returnPressed.connect(self._on_login_clicked)
        self._uid_input.returnPressed.connect(self._on_login_clicked)
        layout.addRow(btn_login)
        return page

    def _build_first_run_page(self) -> QWidget:
        page   = QWidget()
        layout = QFormLayout(page)
        layout.setSpacing(12)

        subtitle = QLabel("No users found. Create the first admin account.")
        subtitle.setWordWrap(True)
        layout.addRow(subtitle)

        self._fa_uid   = QLineEdit(); self._fa_uid.setPlaceholderText("Numeric ID")
        self._fa_first = QLineEdit(); self._fa_first.setPlaceholderText("First name")
        self._fa_last  = QLineEdit(); self._fa_last.setPlaceholderText("Last name")
        self._fa_pw    = QLineEdit(); self._fa_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._fa_pw.setPlaceholderText("Password")

        layout.addRow("User ID:",     self._fa_uid)
        layout.addRow("First name:",  self._fa_first)
        layout.addRow("Last name:",   self._fa_last)
        layout.addRow("Password:",    self._fa_pw)

        btn_create = QPushButton("Create Admin & Login")
        btn_create.setMinimumHeight(44)
        btn_create.clicked.connect(self._on_first_admin_clicked)
        layout.addRow(btn_create)
        return page

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_login_clicked(self) -> None:
        self._error_label.setVisible(False)
        self.login_submitted.emit(
            self._uid_input.text().strip(),
            self._pw_input.text(),
        )

    def _on_first_admin_clicked(self) -> None:
        self._error_label.setVisible(False)
        self.first_admin_submitted.emit(
            self._fa_uid.text().strip(),
            self._fa_first.text().strip(),
            self._fa_last.text().strip(),
            self._fa_pw.text(),
        )

    @staticmethod
    def _stylesheet() -> str:
        return """
            QDialog  { background-color: white; color: black; }
            QLabel   { color: black; }
            QLineEdit {
                border: 1px solid #cccccc; border-radius: 4px;
                padding: 6px; font-size: 13px; color: black; background: white;
            }
            QPushButton {
                background-color: #905BA9; border: none; color: white;
                padding: 8px 16px; font-size: 14px; border-radius: 4px;
            }
            QPushButton:hover    { background-color: #7A4D92; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """

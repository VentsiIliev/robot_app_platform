from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton,
    QStackedWidget, QTabWidget, QWidget, QMessageBox,
)

from src.engine.auth.i_authenticated_user import IAuthenticatedUser

# ── Stack page indices ────────────────────────────────────────────────────────
_PAGE_FIRST_RUN = 0
_PAGE_TABS      = 1

# ── Tab indices ───────────────────────────────────────────────────────────────
_TAB_LOGIN = 0
_TAB_QR    = 1

_QR_POLL_MS = 2000   # poll interval for automatic QR scanning


class LoginView(QDialog):
    """
    Login dialog matching the legacy layout:

      ┌──────────────┬──────────────────────────────────┐
      │              │  [first-run page]                │
      │  Logo panel  │   ── or ──                       │
      │  (gradient)  │  [Tab: Normal login | QR login]  │
      └──────────────┴──────────────────────────────────┘

    Signals
    -------
    login_submitted(user_id, password)       — normal login button
    qr_scan_requested()                      — fired by QTimer while QR tab is visible
    qr_tab_activated()                       — user switched to QR tab (triggers robot move)
    first_admin_submitted(id, fn, ln, pw)    — first-run form submit
    """

    login_submitted       = pyqtSignal(str, str)
    qr_scan_requested     = pyqtSignal()
    qr_tab_activated      = pyqtSignal()
    first_admin_submitted = pyqtSignal(str, str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setMinimumSize(700, 440)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self._allow_close = False
        self._result_user: Optional[IAuthenticatedUser] = None

        self._qr_timer = QTimer(self)
        self._qr_timer.setInterval(_QR_POLL_MS)
        self._qr_timer.timeout.connect(self.qr_scan_requested)

        self._setup_ui()
        self.setStyleSheet(self._stylesheet())

    # ── Controller-facing API ────────────────────────────────────────────────

    def show_login(self) -> None:
        """Show the normal-login/QR tab panel (not first-run)."""
        self._stack.setCurrentIndex(_PAGE_TABS)
        self._tabs.setCurrentIndex(_TAB_LOGIN)

    def show_first_run(self) -> None:
        """Show the first-admin creation panel."""
        self._stack.setCurrentIndex(_PAGE_FIRST_RUN)

    def show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def accept_login(self, user: IAuthenticatedUser) -> None:
        self._result_user = user
        self._allow_close = True
        self._stop_qr_scanning()
        self._error_label.setVisible(False)
        self.accept()

    def result_user(self) -> Optional[IAuthenticatedUser]:
        return self._result_user

    # ── QR scanning control (called by controller) ───────────────────────────

    def start_qr_scanning(self) -> None:
        if not self._qr_timer.isActive():
            self._qr_timer.start()

    def stop_qr_scanning(self) -> None:
        self._stop_qr_scanning()

    # ── UI construction ──────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_logo_panel(), stretch=1)
        root.addWidget(self._build_right_panel(), stretch=2)

    def _build_logo_panel(self) -> QWidget:
        panel  = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._logo_label = QLabel("Robot\nPlatform")
        self._logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont(); f.setPointSize(22); f.setBold(True)
        self._logo_label.setFont(f)
        self._logo_label.setStyleSheet("color: #4a2060;")
        layout.addWidget(self._logo_label)

        panel.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #d5c6f6, stop: 1 #b8b5e0
                );
            }
        """)
        return panel

    def _build_right_panel(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("QWidget { background-color: white; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_first_run_page())   # _PAGE_FIRST_RUN = 0
        self._stack.addWidget(self._build_tabs_widget())      # _PAGE_TABS      = 1
        layout.addWidget(self._stack)

        self._error_label = QLabel()
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setStyleSheet("color: #c0392b; font-weight: bold; padding: 4px;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        return container

    def _build_tabs_widget(self) -> QTabWidget:
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_login_tab(), "Login")
        self._tabs.addTab(self._build_qr_tab(),    "QR Login")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        return self._tabs

    def _build_login_tab(self) -> QWidget:
        page   = QWidget()
        layout = QFormLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        title = QLabel("Login")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont(); f.setPointSize(16); f.setBold(True)
        title.setFont(f)
        layout.addRow(title)

        self._uid_input = QLineEdit()
        self._uid_input.setPlaceholderText("Numeric user ID")
        self._uid_input.setFixedHeight(40)
        layout.addRow("User ID:", self._uid_input)

        self._pw_input = QLineEdit()
        self._pw_input.setPlaceholderText("Password")
        self._pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_input.setFixedHeight(40)
        layout.addRow("Password:", self._pw_input)

        btn = QPushButton("Login")
        btn.setMinimumHeight(48)
        btn.clicked.connect(self._on_login_clicked)
        self._uid_input.returnPressed.connect(self._on_login_clicked)
        self._pw_input.returnPressed.connect(self._on_login_clicked)
        layout.addRow(btn)
        return page

    def _build_qr_tab(self) -> QWidget:
        page   = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        info = QLabel("Scanning for QR code…\nPoint the camera at a user QR code to log in.")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        f = QFont(); f.setPointSize(13)
        info.setFont(f)
        layout.addStretch(1)
        layout.addWidget(info)
        layout.addStretch(1)
        return page

    def _build_first_run_page(self) -> QWidget:
        page   = QWidget()
        layout = QFormLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(14)

        title = QLabel("First-time setup")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont(); f.setPointSize(15); f.setBold(True)
        title.setFont(f)
        layout.addRow(title)

        subtitle = QLabel("No users found. Create the first admin account.")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addRow(subtitle)

        self._fa_uid   = QLineEdit(); self._fa_uid.setPlaceholderText("Numeric ID");    self._fa_uid.setFixedHeight(40)
        self._fa_first = QLineEdit(); self._fa_first.setPlaceholderText("First name");  self._fa_first.setFixedHeight(40)
        self._fa_last  = QLineEdit(); self._fa_last.setPlaceholderText("Last name");    self._fa_last.setFixedHeight(40)
        self._fa_pw    = QLineEdit(); self._fa_pw.setEchoMode(QLineEdit.EchoMode.Password); self._fa_pw.setFixedHeight(40)
        self._fa_pw.setPlaceholderText("Password")

        layout.addRow("User ID:",    self._fa_uid)
        layout.addRow("First name:", self._fa_first)
        layout.addRow("Last name:",  self._fa_last)
        layout.addRow("Password:",   self._fa_pw)

        btn = QPushButton("Create Admin & Login")
        btn.setMinimumHeight(48)
        btn.clicked.connect(self._on_first_admin_clicked)
        self._fa_pw.returnPressed.connect(self._on_first_admin_clicked)
        layout.addRow(btn)
        return page

    # ── Internal slots ───────────────────────────────────────────────────────

    def _on_tab_changed(self, index: int) -> None:
        self._error_label.setVisible(False)
        if index == _TAB_QR:
            confirmed = QMessageBox.warning(
                self,
                "Warning",
                "The robot will move to the login position.\n"
                "Please ensure the area is clear before proceeding.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if confirmed == QMessageBox.StandardButton.Ok:
                self.qr_tab_activated.emit()
                self.start_qr_scanning()
            else:
                self._tabs.setCurrentIndex(_TAB_LOGIN)
        else:
            self._stop_qr_scanning()

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

    def _stop_qr_scanning(self) -> None:
        if self._qr_timer.isActive():
            self._qr_timer.stop()

    # ── Block ESC / accidental close ─────────────────────────────────────────

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        if not self._allow_close:
            event.ignore()
            return
        super().closeEvent(event)

    # ── Responsive logo ──────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:
        size = max(14, min(int(self.width() * 0.04), 26))
        f = self._logo_label.font()
        f.setPointSize(size)
        self._logo_label.setFont(f)
        super().resizeEvent(event)

    # ── Stylesheet ───────────────────────────────────────────────────────────

    @staticmethod
    def _stylesheet() -> str:
        return """
            QDialog { background-color: white; color: black; }
            QLabel  { color: black; }
            QLineEdit {
                border: 2px solid purple; border-radius: 10px;
                padding: 6px; font-size: 14px; color: black; background: white;
            }
            QTabWidget::pane { border: 1px solid #cccccc; }
            QTabBar::tab {
                background: #f0f0f0; color: black;
                padding: 10px 20px; font-size: 13px;
            }
            QTabBar::tab:selected { background: white; font-weight: bold; border-bottom: 2px solid #905BA9; }
            QPushButton {
                background-color: #905BA9; border: none; color: white;
                padding: 8px 16px; font-size: 14px; border-radius: 4px;
            }
            QPushButton:hover    { background-color: #7A4D92; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """

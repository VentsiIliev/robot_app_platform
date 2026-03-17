import os
from typing import Optional

import cv2
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QEvent, QCoreApplication
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton,
    QSizePolicy, QStackedWidget, QTabWidget, QWidget, QMessageBox,
)

from pl_gui.utils.utils_widgets.camera_view import CameraView


class _FeedOnlyCameraView(CameraView):
    """CameraView with zoom, pan, and toolbar disabled — feed display only."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._toolbar.hide()

    def wheelEvent(self, event) -> None:
        event.ignore()

    def mousePressEvent(self, event) -> None:
        event.ignore()

    def mouseMoveEvent(self, event) -> None:
        event.ignore()

    def mouseReleaseEvent(self, event) -> None:
        event.ignore()

from src.engine.auth.i_authenticated_user import IAuthenticatedUser

# ── Asset paths ───────────────────────────────────────────────────────────────
_RESOURCES = os.path.join(os.path.dirname(__file__), "..", "..", "base", "resources")
_LOGO_PATH          = os.path.join(_RESOURCES, "logo.ico")
_MACHINE_IMAGE_PATH = os.path.join(_RESOURCES, "MACHINE_BUTTONS_1.png")

# ── Stack page indices ────────────────────────────────────────────────────────
_PAGE_SETUP     = 0
_PAGE_FIRST_RUN = 1
_PAGE_TABS      = 2

# ── Tab indices ───────────────────────────────────────────────────────────────
_TAB_LOGIN = 0
_TAB_QR    = 1

_QR_POLL_MS = 2000


class LoginView(QDialog):
    """
    Login dialog layout:

      ┌──────────────┬──────────────────────────────────────┐
      │              │  Page 0: Setup steps                 │
      │  Logo panel  │  Page 1: First-admin creation        │
      │  (gradient)  │  Page 2: [Login tab | QR login tab]  │
      └──────────────┴──────────────────────────────────────┘

    Signals
    -------
    setup_confirmed()                        — user clicked "Next" on setup page
    login_submitted(user_id, password)       — normal login button / Enter
    qr_scan_requested()                      — fired by QTimer while QR tab active
    qr_tab_activated()                       — user confirmed QR tab switch
    first_admin_submitted(id, fn, ln, pw)    — first-run form submit
    """

    setup_confirmed       = pyqtSignal()
    login_submitted       = pyqtSignal(str, str)
    qr_scan_requested     = pyqtSignal()
    qr_tab_activated      = pyqtSignal()
    first_admin_submitted = pyqtSignal(str, str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setMinimumSize(700, 460)
        self._allow_close = False
        self._result_user: Optional[IAuthenticatedUser] = None

        self._qr_timer = QTimer(self)
        self._qr_timer.setInterval(_QR_POLL_MS)
        self._qr_timer.timeout.connect(self.qr_scan_requested)

        self._logo_pixmap: Optional[QPixmap] = None

        self._setup_ui()
        self.setStyleSheet(self._stylesheet())

    # ── Controller-facing API ────────────────────────────────────────────────

    def show_setup(self) -> None:
        self._stack.setCurrentIndex(_PAGE_SETUP)

    def show_login(self) -> None:
        self._stack.setCurrentIndex(_PAGE_TABS)
        self._tabs.setCurrentIndex(_TAB_LOGIN)

    def show_first_run(self) -> None:
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
        self.retranslateUi()

    # ── Logo panel ───────────────────────────────────────────────────────────

    def _build_logo_panel(self) -> QWidget:
        panel  = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(16, 16, 16, 16)

        self._logo_label = QLabel()
        self._logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = QPixmap(_LOGO_PATH)
        if not pixmap.isNull():
            self._logo_pixmap = pixmap
            self._logo_label.setPixmap(
                pixmap.scaled(150, 150,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )
        else:
            # Fallback text if asset not found
            f = QFont(); f.setPointSize(22); f.setBold(True)
            self._logo_label.setFont(f)
            self._logo_label.setText("Robot\nPlatform")
            self._logo_label.setStyleSheet("color: #4a2060;")

        layout.addWidget(self._logo_label)

        panel.setStyleSheet("""
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #d5c6f6, stop: 1 #b8b5e0
            );
        """)
        return panel

    # ── Right panel (stacked) ─────────────────────────────────────────────────

    def _build_right_panel(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background-color: white;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_setup_page())      # _PAGE_SETUP     = 0
        self._stack.addWidget(self._build_first_run_page())  # _PAGE_FIRST_RUN = 1
        self._stack.addWidget(self._build_tabs_widget())     # _PAGE_TABS      = 2
        layout.addWidget(self._stack)

        self._error_label = QLabel()
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setStyleSheet(
            "color: #c0392b; font-weight: bold; padding: 4px;"
        )
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        return container

    # ── Setup page ────────────────────────────────────────────────────────────

    def _build_setup_page(self) -> QWidget:
        page   = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)

        # Machine image
        self._machine_label = QLabel()
        self._machine_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        machine_px = QPixmap(_MACHINE_IMAGE_PATH)
        if not machine_px.isNull():
            self._machine_pixmap = machine_px
            self._machine_label.setPixmap(
                machine_px.scaled(300, 300,
                                  Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self._machine_pixmap = None
            self._machine_label.setText("[Machine image not found]")
            self._machine_label.setStyleSheet("color: grey; font-size: 12px;")
        layout.addWidget(self._machine_label)

        # Instruction
        self._setup_instruction = QLabel()
        self._setup_instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._setup_instruction.setWordWrap(True)
        f = QFont(); f.setPointSize(13)
        self._setup_instruction.setFont(f)
        layout.addWidget(self._setup_instruction)

        layout.addStretch(1)

        # TODO: remove once physical blue-button signal is wired
        self._btn_sim = QPushButton()
        self._btn_sim.setFixedHeight(44)
        self._btn_sim.setToolTip("Temporary — simulates the physical blue button press")
        self._btn_sim.setStyleSheet("""
            QPushButton {
                background-color: #1565C0; color: white;
                border: none; border-radius: 6px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #0D47A1; }
        """)
        self._btn_sim.clicked.connect(self._on_setup_next_clicked)
        layout.addWidget(self._btn_sim)

        return page

    # ── First-run page ────────────────────────────────────────────────────────

    def _build_first_run_page(self) -> QWidget:
        page   = QWidget()
        layout = QFormLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(14)

        self._fr_title = QLabel()
        self._fr_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont(); f.setPointSize(15); f.setBold(True)
        self._fr_title.setFont(f)
        layout.addRow(self._fr_title)

        self._fr_subtitle = QLabel()
        self._fr_subtitle.setWordWrap(True)
        self._fr_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addRow(self._fr_subtitle)

        self._fa_uid   = QLineEdit(); self._fa_uid.setFixedHeight(40)
        self._fa_first = QLineEdit(); self._fa_first.setFixedHeight(40)
        self._fa_last  = QLineEdit(); self._fa_last.setFixedHeight(40)
        self._fa_pw    = QLineEdit(); self._fa_pw.setFixedHeight(40)
        self._fa_pw.setEchoMode(QLineEdit.EchoMode.Password)

        self._fr_label_uid   = QLabel(); layout.addRow(self._fr_label_uid,   self._fa_uid)
        self._fr_label_first = QLabel(); layout.addRow(self._fr_label_first, self._fa_first)
        self._fr_label_last  = QLabel(); layout.addRow(self._fr_label_last,  self._fa_last)
        self._fr_label_pw    = QLabel(); layout.addRow(self._fr_label_pw,    self._fa_pw)

        self._fr_btn = self._primary_btn("")
        self._fr_btn.setMinimumHeight(48)
        self._fr_btn.clicked.connect(self._on_first_admin_clicked)
        self._fa_pw.returnPressed.connect(self._on_first_admin_clicked)
        layout.addRow(self._fr_btn)
        return page

    # ── Login / QR tabs ───────────────────────────────────────────────────────

    def _build_tabs_widget(self) -> QTabWidget:
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_login_tab(), "Login")
        self._tabs.addTab(self._build_qr_tab(),    "QR Login")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        return self._tabs

    def _build_login_tab(self) -> QWidget:
        page   = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(14)

        self._login_title = QLabel()
        self._login_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont(); f.setPointSize(16); f.setBold(True)
        self._login_title.setFont(f)
        layout.addWidget(self._login_title)

        self._uid_label = QLabel()
        layout.addWidget(self._uid_label)
        self._uid_input = QLineEdit()
        self._uid_input.setFixedHeight(40)
        layout.addWidget(self._uid_input)

        self._pw_label = QLabel()
        layout.addWidget(self._pw_label)
        self._pw_input = QLineEdit()
        self._pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_input.setFixedHeight(40)
        layout.addWidget(self._pw_input)

        self._login_btn = self._primary_btn("")
        self._login_btn.setFixedHeight(52)
        self._login_btn.clicked.connect(self._on_login_clicked)
        self._uid_input.returnPressed.connect(self._on_login_clicked)
        self._pw_input.returnPressed.connect(self._on_login_clicked)
        layout.addWidget(self._login_btn)
        layout.addStretch(1)
        return page

    def _build_qr_tab(self) -> QWidget:
        page   = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        self._qr_info = QLabel()
        self._qr_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_info.setWordWrap(True)
        layout.addWidget(self._qr_info)

        self._camera_view = _FeedOnlyCameraView()
        self._camera_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._camera_view, stretch=1)

        return page

    def update_camera_frame(self, frame) -> None:
        """Push a BGR numpy frame to the camera view. Called from the controller."""
        if frame is None:
            return
        try:
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg  = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self._camera_view.set_frame(QPixmap.fromImage(qimg))
        except RuntimeError:
            pass  # C++ widget already deleted — queued signal arrived after teardown

    # ── Internal slots ───────────────────────────────────────────────────────

    def _on_setup_next_clicked(self) -> None:
        self._error_label.setVisible(False)
        self.setup_confirmed.emit()

    def _on_tab_changed(self, index: int) -> None:
        self._error_label.setVisible(False)
        if index == _TAB_QR:
            confirmed = QMessageBox.warning(
                self,
                self._t("Warning"),
                self._t("The robot will move to the login position.\n"
                        "Please ensure the area is clear before proceeding."),
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

    # ── Localization ─────────────────────────────────────────────────────────

    @staticmethod
    def _t(text: str) -> str:
        translated = QCoreApplication.translate("Login", text)
        return translated or text

    def retranslateUi(self, *_) -> None:
        self.setWindowTitle(self._t("Login"))
        self._setup_instruction.setText(self._t("Press the blue button on the machine to continue."))
        self._btn_sim.setText(self._t("⬤  Simulate Blue Button"))
        self._fr_title.setText(self._t("First-time setup"))
        self._fr_subtitle.setText(self._t("No users found. Create the first admin account."))
        self._fr_label_uid.setText(self._t("User ID:"))
        self._fr_label_first.setText(self._t("First name:"))
        self._fr_label_last.setText(self._t("Last name:"))
        self._fr_label_pw.setText(self._t("Password:"))
        self._fr_btn.setText(self._t("Create Admin & Login"))
        self._login_title.setText(self._t("Login"))
        self._uid_label.setText(self._t("User ID:"))
        self._pw_label.setText(self._t("Password:"))
        self._login_btn.setText(self._t("Login"))
        self._qr_info.setText(self._t("Point the camera at a user QR code to log in automatically."))
        self._tabs.setTabText(_TAB_LOGIN, self._t("Login"))
        self._tabs.setTabText(_TAB_QR,    self._t("QR Login"))
        self._uid_input.setPlaceholderText(self._t("Numeric user ID"))
        self._pw_input.setPlaceholderText(self._t("Password"))
        self._fa_uid.setPlaceholderText(self._t("Numeric ID"))
        self._fa_first.setPlaceholderText(self._t("First name"))
        self._fa_last.setPlaceholderText(self._t("Last name"))
        self._fa_pw.setPlaceholderText(self._t("Password"))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

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

    # ── Responsive resize ─────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:
        if self._logo_pixmap:
            size = int(min(self.width() * 0.18, 180))
            self._logo_label.setPixmap(
                self._logo_pixmap.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        if hasattr(self, "_machine_pixmap") and self._machine_pixmap:
            size = int(min(self.height() * 0.45, 320))
            self._machine_label.setPixmap(
                self._machine_pixmap.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        super().resizeEvent(event)

    # ── Button factory ────────────────────────────────────────────────────────

    @staticmethod
    def _primary_btn(text: str) -> QPushButton:
        """Purple-styled button — style applied directly to avoid cascade issues."""
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #905BA9; border: none; color: white;
                padding: 8px 16px; font-size: 14px; border-radius: 4px;
            }
            QPushButton:hover    { background-color: #7A4D92; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """)
        return btn

    # ── Stylesheet ────────────────────────────────────────────────────────────

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
            QTabBar::tab:selected {
                background: white; font-weight: bold;
                border-bottom: 2px solid #905BA9;
            }
            QPushButton {
                background-color: #905BA9; border: none; color: white;
                padding: 8px 16px; font-size: 14px; border-radius: 4px;
            }
            QPushButton:hover    { background-color: #7A4D92; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """

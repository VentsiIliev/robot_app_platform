"""
Compatibility shims for the legacy login package.

Replaces all unavailable frontend/communication_layer/modules dependencies
with lightweight stand-ins so the login UI can run without the old platform.
"""
import json
import os
from enum import Enum
from typing import Any, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)


# ── Translatable base classes ─────────────────────────────────────────────────

class TranslatableDialog(QDialog):
    def __init__(self, *args, auto_retranslate: bool = False, **kwargs):
        super().__init__(*args, **kwargs)

    def init_translations(self) -> None:
        self.retranslate()

    def retranslate(self) -> None:
        pass


class TranslatableWidget(QWidget):
    def __init__(self, parent=None, auto_retranslate: bool = False):
        super().__init__(parent)

    def init_translations(self) -> None:
        self.retranslate()

    def retranslate(self) -> None:
        pass


class TranslatableObject:
    def __init__(self):
        pass

    def tr(self, text: str) -> str:  # noqa: D401
        return text

    def init_translations(self) -> None:
        pass


# ── Translation key stubs ─────────────────────────────────────────────────────

class _NS:
    """Generic namespace that returns its attribute name as a string."""
    def __getattr__(self, item: str) -> str:
        return item.replace("_", " ").title()


class TranslationKeys:
    Auth      = _NS()
    Warning   = _NS()
    Navigation = _NS()
    Setup     = _NS()


# Concrete strings used in the login files
TranslationKeys.Auth.LOGIN                          = "Login"
TranslationKeys.Auth.ID                             = "User ID"
TranslationKeys.Auth.PASSWORD                       = "Password"
TranslationKeys.Auth.SCAN_QR_TO_LOGIN               = "Scan QR code to log in"
TranslationKeys.Auth.ENTER_ID_AND_PASSWORD          = "Please enter your ID and password."
TranslationKeys.Auth.INVALID_LOGIN_ID               = "User ID must be numeric."
TranslationKeys.Auth.INCORRECT_PASSWORD             = "Incorrect password."
TranslationKeys.Auth.USER_NOT_FOUND                 = "User not found."
TranslationKeys.Warning.WARNING                     = "Warning"
TranslationKeys.Warning.THE_ROBOT_WILL_START_MOVING_TO_THE_LOGIN_POSITION = \
    "The robot will move to the login position."
TranslationKeys.Warning.PLEASE_ENSURE_THE_AREA_IS_CLEAR_BEFORE_PROCEEDING = \
    "Please ensure the area is clear before proceeding."
TranslationKeys.Warning.CANCEL                      = "Cancel"
TranslationKeys.Navigation.NEXT                     = "Next"
TranslationKeys.Setup.SETUP_FIRST_STEP              = "Press the blue button on the machine to continue."


# ── CustomFeedbackDialog ──────────────────────────────────────────────────────

class DialogType(Enum):
    WARNING = "warning"
    INFO    = "info"
    SUCCESS = "success"
    ERROR   = "error"


class CustomFeedbackDialog(QDialog):
    def __init__(
        self,
        parent=None,
        dialog_type: DialogType = DialogType.INFO,
        title: str = "",
        message: str = "",
        info_text: str = "",
        ok_text: str = "OK",
        cancel_text: Optional[str] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl = QLabel(message)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        if info_text:
            info = QLabel(info_text)
            info.setWordWrap(True)
            info.setStyleSheet("color: grey; font-size: 12px;")
            layout.addWidget(info)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton(ok_text)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        if cancel_text:
            btn_cancel = QPushButton(cancel_text)
            btn_cancel.clicked.connect(self.reject)
            btn_row.addWidget(btn_cancel)

        layout.addLayout(btn_row)


# ── Header stub ───────────────────────────────────────────────────────────────

class Header(QWidget):
    def __init__(self, width: int = 0, height: int = 0, *args, **kwargs):
        super().__init__()
        self.setFixedHeight(48)
        self.setStyleSheet("background-color: #905BA9;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)

        title = QLabel("Robot Platform")
        title.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        layout.addStretch()

        # Attributes accessed by LoginWindow
        self.menu_button          = QPushButton()
        self.dashboardButton      = QPushButton()
        self.power_toggle_button  = QPushButton()

        for btn in (self.menu_button, self.dashboardButton, self.power_toggle_button):
            btn.setVisible(False)
            layout.addWidget(btn)


# ── ToastWidget ───────────────────────────────────────────────────────────────

class ToastWidget(QLabel):
    """Floating message that auto-hides after `duration` seconds."""

    def __init__(self, parent: QWidget, message: str, duration: int = 2):
        super().__init__(message, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "background-color: rgba(60,60,60,200); color: white; "
            "border-radius: 8px; padding: 8px 16px; font-size: 13px;"
        )
        self.adjustSize()
        self._reposition(parent)
        QTimer.singleShot(duration * 1000, self.hide)

    def _reposition(self, parent: QWidget) -> None:
        pw, ph = parent.width(), parent.height()
        self.adjustSize()
        x = (pw - self.width())  // 2
        y =  ph - self.height() - 40
        self.move(x, max(0, y))
        self.raise_()


# ── Widgets ───────────────────────────────────────────────────────────────────

# FocusLineEdit → plain QLineEdit (no virtual keyboard)
from PyQt6.QtWidgets import QLineEdit as FocusLineEdit  # noqa: E402


class MaterialButton(QPushButton):
    """QPushButton with the legacy purple styling."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: #905BA9; color: white; border: none;
                border-radius: 6px; padding: 8px 20px; font-size: 14px;
            }
            QPushButton:hover    { background-color: #7A4D92; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """)


# ── CameraFeed stub ───────────────────────────────────────────────────────────

class CameraFeedConfig:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class CameraFeed(QLabel):
    """Placeholder shown when no real camera driver is available."""

    def __init__(self, cameraFeedConfig=None, updateCallback=None, toggleCallback=None, parent=None):
        super().__init__("[Camera feed — not available in standalone mode]", parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(320, 180)
        self.setStyleSheet(
            "background: #222; color: #aaa; font-size: 12px; border-radius: 6px;"
        )


# ── Global style constant ─────────────────────────────────────────────────────

FONT = "Arial"


# ── Icon path stubs (None = no icon) ─────────────────────────────────────────

LOGO                = None
LOGIN_BUTTON        = None
LOGIN_QR_BUTTON     = None
MACHINE_BUTTONS_IMAGE = None


# ── MessageBroker stub ────────────────────────────────────────────────────────

class MessageBroker:
    def publish(self, topic: str, *args, **kwargs) -> None:
        pass


# ── JSON loader ───────────────────────────────────────────────────────────────

def load_json_file(path: str, default: Any = None, debug: bool = False) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        if debug:
            print(f"[load_json_file] Could not load {path!r}: {exc}")
        return default if default is not None else {}


# ── Endpoint & response stubs ─────────────────────────────────────────────────

class _Endpoints:
    def __getattr__(self, item: str) -> str:
        return item


camera_endpoints = _Endpoints()
auth_endpoints   = _Endpoints()


class Constants:
    RESPONSE_STATUS_SUCCESS = "success"


class _MockResponse:
    def __init__(self, status: str, data: dict):
        self.status = status
        self.data   = data

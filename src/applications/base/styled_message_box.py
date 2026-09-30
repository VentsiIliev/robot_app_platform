from dataclasses import dataclass
from typing import Sequence

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE, BORDER, ERROR_COLOR, GHOST_BTN_STYLE, PRIMARY,
    PRIMARY_DARK,
    SECONDARY_BG, TEXT_COLOR, TEXT_ON_PRIMARY,
)

_ACCENT = PRIMARY
_ACCENT_H = PRIMARY_DARK
_BG = TEXT_ON_PRIMARY
_TEXT = TEXT_COLOR

_STYLE = f"""
    QMessageBox {{
        background-color: {_BG};
        color: {_TEXT};
    }}
    QMessageBox QLabel {{
        color: {_TEXT};
        font-size: 13px;
        min-width: 280px;
    }}
    QMessageBox QPushButton {{
        background-color: {_ACCENT};
        color: white;
        border: none;
        border-radius: 4px;
        padding: 8px 20px;
        font-size: 13px;
        min-width: 90px;
        min-height: 36px;
    }}
    QMessageBox QPushButton:hover {{
        background-color: {_ACCENT_H};
    }}
    QMessageBox QPushButton:pressed {{
        background-color: {_ACCENT_H};
    }}
"""


def _make(icon, title: str, text: str, parent: QWidget) -> QMessageBox:
    mb = QMessageBox(icon, title, text, parent=parent)
    mb.setStyleSheet(_STYLE)
    return mb


def make_warning(parent: QWidget, title: str, text: str) -> QMessageBox:
    return _make(QMessageBox.Icon.Warning, title, text, parent)


def make_info(parent: QWidget, title: str, text: str) -> QMessageBox:
    return _make(QMessageBox.Icon.Information, title, text, parent)


def make_critical(parent: QWidget, title: str, text: str) -> QMessageBox:
    return _make(QMessageBox.Icon.Critical, title, text, parent)


@dataclass(frozen=True)
class DialogAction:
    key: str
    text: str
    primary: bool = False
    full_width: bool = False


class ActionWarningDialog(QDialog):
    """Optional action layout for warnings that need a clear next step."""

    def __init__(
        self, parent: QWidget, title: str, text: str, *,
        heading: str, guidance: str = "", status: str = "",
        actions: Sequence[DialogAction],
    ) -> None:
        super().__init__(parent)
        self.selected_action: str | None = None
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(540)
        self.setStyleSheet(f"QDialog {{ background: white; color: {TEXT_COLOR}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        icon = QLabel("!")
        icon.setObjectName("warningIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(44, 44)
        icon.setStyleSheet(
            f"background: {ERROR_COLOR}; color: {TEXT_ON_PRIMARY}; "
            "border-radius: 22px; font-size: 22px; font-weight: bold;"
        )
        header.addWidget(icon)
        titles = QVBoxLayout()
        heading_label = QLabel(heading)
        heading_label.setObjectName("warningHeading")
        heading_label.setStyleSheet(
            f"color: {ERROR_COLOR}; font-size: 12px; font-weight: bold;"
        )
        titles.addWidget(heading_label)
        title_label = QLabel(title)
        title_label.setObjectName("warningTitle")
        title_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 20px; font-weight: bold;"
        )
        titles.addWidget(title_label)
        header.addLayout(titles, 1)
        layout.addLayout(header)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(divider)
        body = QLabel(text)
        body.setObjectName("warningBody")
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 14px;")
        layout.addWidget(body)
        if guidance:
            guidance_label = QLabel(guidance)
            guidance_label.setObjectName("warningGuidance")
            guidance_label.setWordWrap(True)
            guidance_label.setStyleSheet(f"color: {PRIMARY}; font-size: 13px;")
            layout.addWidget(guidance_label)
        if status:
            status_label = QLabel(status)
            status_label.setObjectName("warningStatus")
            status_label.setStyleSheet(
                f"background: {SECONDARY_BG}; color: {ERROR_COLOR}; "
                "padding: 10px; font-size: 12px; font-weight: bold;"
            )
            layout.addWidget(status_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        for action in actions:
            button = QPushButton(action.text)
            button.setObjectName(f"warningAction_{action.key}")
            button.setProperty("action_key", action.key)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(ACTION_BTN_STYLE if action.primary else GHOST_BTN_STYLE)
            button.clicked.connect(self._on_action_clicked)
            if action.full_width:
                if button_row.count():
                    layout.addLayout(button_row)
                    button_row = QHBoxLayout()
                layout.addWidget(button)
            else:
                button_row.addWidget(button, 1)
        if button_row.count():
            layout.addLayout(button_row)

    def _on_action_clicked(self) -> None:
        button = self.sender()
        self.selected_action = button.property("action_key") if button else None
        self.accept()


def show_warning(
    parent: QWidget, title: str, text: str, *,
    heading: str = "", guidance: str = "", status: str = "",
    actions: Sequence[DialogAction] | None = None,
) -> str | None:
    if actions is None:
        make_warning(parent, title, text).exec()
        return None
    dialog = ActionWarningDialog(
        parent, title, text, heading=heading, guidance=guidance,
        status=status, actions=actions,
    )
    dialog.exec()
    return dialog.selected_action


def show_info(parent: QWidget, title: str, text: str) -> None:
    mb = make_info(parent, title, text)
    mb.exec()


def show_critical(parent: QWidget, title: str, text: str) -> None:
    mb = make_critical(parent, title, text)
    mb.exec()


def ask_yes_no(parent: QWidget, title: str, text: str,
               default_no: bool = True) -> bool:
    mb = _make(QMessageBox.Icon.Question, title, text, parent)
    mb.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    mb.setDefaultButton(
        QMessageBox.StandardButton.No if default_no
        else QMessageBox.StandardButton.Yes
    )
    return mb.exec() == QMessageBox.StandardButton.Yes

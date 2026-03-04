from PyQt6.QtWidgets import QMessageBox, QWidget

_ACCENT   = "#905BA9"
_ACCENT_H = "#7A4D92"
_BG       = "#ffffff"
_TEXT     = "#111111"
_BORDER   = "#cccccc"
_MUTED    = "#666666"

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


def show_warning(parent: QWidget, title: str, text: str) -> None:
    mb = _make(QMessageBox.Icon.Warning, title, text, parent)
    mb.exec()


def show_info(parent: QWidget, title: str, text: str) -> None:
    mb = _make(QMessageBox.Icon.Information, title, text, parent)
    mb.exec()


def show_critical(parent: QWidget, title: str, text: str) -> None:
    mb = _make(QMessageBox.Icon.Critical, title, text, parent)
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
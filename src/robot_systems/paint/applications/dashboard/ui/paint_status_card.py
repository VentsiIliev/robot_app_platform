from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pl_gui.settings.settings_view.styles import (
    BG_COLOR,
    BORDER,
    PRIMARY,
    TEXT_COLOR,
)


_ERROR = "#C62828"
_MUTED = "#6B7280"


_CARD_STYLE = f"""
QWidget {{
    background: white;
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QLabel {{
    background: transparent;
    border: none;
    color: {TEXT_COLOR};
}}
"""


def _badge_style(color: str) -> str:
    return f"""
QLabel {{
    background: {color};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14pt;
    font-weight: bold;
}}
"""


_TILE_STYLE = f"""
QFrame {{
    background: {BG_COLOR};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QLabel {{
    background: transparent;
    border: none;
}}
"""


_SECTION_TITLE_STYLE = f"font-size: 9pt; color: {_MUTED}; font-weight: bold;"
_MUTED_STYLE = f"font-size: 9pt; color: {_MUTED};"


class PaintStatusCard(QWidget):

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_CARD_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        self._status = QLabel("READY TO PAINT")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(_badge_style(PRIMARY))
        self._status.setMinimumWidth(220)

        layout.addWidget(self._status)

        self._issue_title = QLabel("")
        self._issue_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._issue_title.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {PRIMARY};")
        self._issue_detail = QLabel("")
        self._issue_detail.setWordWrap(True)
        self._issue_detail.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._issue_detail.setStyleSheet(_MUTED_STYLE)
        self._issue_box = QFrame()
        self._issue_box.setStyleSheet("QFrame { background: transparent; border: none; }")
        self._issue_box.setVisible(False)
        issue_layout = QVBoxLayout(self._issue_box)
        issue_layout.setContentsMargins(0, 0, 0, 0)
        issue_layout.setSpacing(2)
        issue_layout.addWidget(self._issue_title)
        issue_layout.addWidget(self._issue_detail)
        layout.addWidget(self._issue_box, 1)

    def set_state(self, state: str) -> None:
        self._apply_status(state)

    def apply_dashboard_state(self, state) -> None:
        process_state = str(getattr(state, "process_state", "idle") or "idle")

        self._apply_status(process_state)
        issue_title, issue_detail = self._issue_message(process_state)
        self._issue_title.setText(issue_title)
        self._issue_detail.setText(issue_detail)
        self._issue_box.setVisible(bool(issue_title or issue_detail))

    def _apply_status(self, state: str) -> None:
        normalized = str(state or "idle").lower()
        if normalized == "running":
            text, color = "PAINTING", PRIMARY
        elif normalized == "paused":
            text, color = "PAUSED", _MUTED
        elif normalized == "error":
            text, color = "NEEDS ATTENTION", _ERROR
        elif normalized == "stopped":
            text, color = "STOPPED", _MUTED
        else:
            text, color = "READY TO PAINT", PRIMARY
        self._status.setText(text)
        self._status.setStyleSheet(_badge_style(color))

    @staticmethod
    def _issue_message(process_state: str) -> tuple[str, str]:
        if process_state == "error":
            return "Action Required", "Check the message on screen, clear the issue, then reset errors."
        if process_state == "paused":
            return "Paused", "Press Resume to continue or Stop to cancel the job."
        return "", ""

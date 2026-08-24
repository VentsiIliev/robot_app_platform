from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from pl_gui.settings.settings_view.styles import BG_COLOR, BORDER, PRIMARY, TEXT_COLOR


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


class PaintInfoCard(QWidget):
    """Operator-facing placeholder card for paint dashboard expo data."""

    def __init__(self, title: str, value: str, note: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_CARD_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet(_CARD_STYLE)
        outer.addWidget(frame)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._title_label.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {PRIMARY};")

        self._value_label = QLabel(value)
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_label.setStyleSheet("font-size: 16pt; font-weight: bold;")

        self._note_label = QLabel(note)
        self._note_label.setWordWrap(True)
        self._note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._note_label.setStyleSheet(f"font-size: 9pt; color: {_MUTED};")

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"QFrame {{ background: {BORDER}; border: none; }}")

        layout.addWidget(self._title_label)
        layout.addWidget(line)
        layout.addStretch(1)
        layout.addWidget(self._value_label)
        layout.addWidget(self._note_label)
        layout.addStretch(1)

    def set_content(self, title: str, value: str, note: str) -> None:
        self._title_label.setText(title)
        self._value_label.setText(value)
        self._note_label.setText(note)

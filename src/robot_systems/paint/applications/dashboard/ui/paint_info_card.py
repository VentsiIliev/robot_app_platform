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
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_label.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {PRIMARY};")

        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet("font-size: 18pt; font-weight: bold;")

        note_label = QLabel(note)
        note_label.setWordWrap(True)
        note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note_label.setStyleSheet(f"font-size: 9pt; color: {_MUTED};")

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"QFrame {{ background: {BORDER}; border: none; }}")

        layout.addWidget(title_label)
        layout.addWidget(line)
        layout.addStretch(1)
        layout.addWidget(value_label)
        layout.addWidget(note_label)
        layout.addStretch(1)

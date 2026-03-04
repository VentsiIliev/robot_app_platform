from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QWidget

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE, BG_COLOR, BORDER, GHOST_BTN_STYLE, PRIMARY, TEXT_COLOR,
)

DIALOG_INPUT_STYLE = f"""
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: white;
    color: {TEXT_COLOR};
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 11pt;
    min-height: 40px;
}}
QLineEdit:focus, QSpinBox:focus {{ border-color: {PRIMARY}; }}
"""

DIALOG_COMBO_STYLE = f"""
QComboBox {{
    background: white;
    color: {TEXT_COLOR};
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 11pt;
    min-height: 40px;
}}
QComboBox:focus {{ border-color: {PRIMARY}; }}
QComboBox::drop-down {{ border: none; padding-right: 8px; }}
QComboBox QAbstractItemView {{
    background: white;
    border: 2px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {PRIMARY};
    selection-color: white;
    font-size: 11pt;
    padding: 4px;
}}
"""

DIALOG_CHECKBOX_STYLE = f"""
QCheckBox {{
    color: {TEXT_COLOR};
    font-size: 11pt;
    spacing: 10px;
}}
QCheckBox::indicator {{
    width: 22px; height: 22px;
    border: 2px solid {BORDER};
    border-radius: 4px;
    background: white;
}}
QCheckBox::indicator:checked {{
    background: {PRIMARY};
    border-color: {PRIMARY};
}}
QCheckBox::indicator:hover {{ border-color: {PRIMARY}; }}
"""

_DIALOG_BASE_STYLE = f"""
QDialog {{ background: {BG_COLOR}; }}
QLabel  {{ color: {TEXT_COLOR}; font-size: 11pt; font-weight: bold; background: transparent; }}
"""


class AppDialog(QDialog):
    """Base for all app dialogs — consistent styling + standard button row."""

    def __init__(self, title: str, min_width: int = 400, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(min_width)
        self.setStyleSheet(_DIALOG_BASE_STYLE)

    def _build_button_row(self, ok_label: str = "OK", cancel_label: str = "Cancel") -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)
        layout.addStretch()

        cancel_btn = QPushButton(cancel_label)
        cancel_btn.setStyleSheet(GHOST_BTN_STYLE)
        cancel_btn.setMinimumWidth(120)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        ok_btn = QPushButton(ok_label)
        ok_btn.setStyleSheet(ACTION_BTN_STYLE)
        ok_btn.setMinimumWidth(120)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)

        return row
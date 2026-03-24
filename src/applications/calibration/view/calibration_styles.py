from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QWidget

_BG = "#F8F9FA"
_PANEL_BG = "#FFFFFF"
_CAPTION = "color: #888899; font-size: 8pt; background: transparent; padding: 2px 6px;"
_SECTION_LBL = "color: #1A1A2E; font-size: 9pt; font-weight: bold; background: transparent; padding: 4px 0;"
_SECTION_HINT = "color: #666688; font-size: 8.5pt; background: transparent; padding: 0 0 4px 0;"
_LOG_STYLE = """
QTextEdit {
    background: #F3F4F8;
    color: #1A1A2E;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    font-family: monospace;
    font-size: 9pt;
    padding: 6px;
}
"""
_DIVIDER_CSS = "background: #E0E0E0;"

_BTN_PRIMARY = """
MaterialButton {
    background: #905BA9;
    color: white;
    border-radius: 8px;
    font-weight: bold;
    min-height: 44px;
}
MaterialButton:hover   { background: #7A4D90; }
MaterialButton:pressed { background: #6B4080; }
"""
_BTN_SECONDARY = """
MaterialButton {
    background: transparent;
    color: #905BA9;
    border: 1.5px solid #905BA9;
    border-radius: 8px;
    font-weight: bold;
    min-height: 44px;
}
MaterialButton:hover { background: rgba(144,91,169,0.08); }
"""
_BTN_SEQUENCE = """
MaterialButton {
    background: #EDE7F6;
    color: #5B3ED6;
    border: 1.5px solid #5B3ED6;
    border-radius: 8px;
    font-weight: bold;
    min-height: 44px;
}
MaterialButton:hover   { background: #E0D6F0; }
MaterialButton:pressed { background: #D4CAE4; }
"""

_BTN_OVERLAY_OFF = """
MaterialButton {
    background: transparent;
    color: #888;
    border: 1.5px solid #CCCCCC;
    border-radius: 8px;
    font-weight: bold;
    min-height: 36px;
}
MaterialButton:hover { background: rgba(0,0,0,0.04); }
"""
_BTN_OVERLAY_ON = """
MaterialButton {
    background: #E8F5E9;
    color: #2E7D32;
    border: 1.5px solid #4CAF50;
    border-radius: 8px;
    font-weight: bold;
    min-height: 36px;
}
MaterialButton:hover { background: #DCEDC8; }
"""

_BTN_DANGER = """
MaterialButton {
    background: #D32F2F;
    color: white;
    border-radius: 8px;
    font-weight: bold;
    min-height: 44px;
}
MaterialButton:hover   { background: #B71C1C; }
MaterialButton:pressed { background: #9A0007; }
MaterialButton:disabled {
    background: #EEEEEE;
    color: #BDBDBD;
    border: 1.5px solid #E0E0E0;
}
"""

_BTN_TEST = """
MaterialButton {
    background: #E8F5E9;
    color: #2E7D32;
    border: 1.5px solid #4CAF50;
    border-radius: 8px;
    font-weight: bold;
    min-height: 44px;
}
MaterialButton:hover   { background: #DCEDC8; }
MaterialButton:pressed { background: #C8E6C9; }
MaterialButton:disabled {
    background: #EEEEEE;
    color: #BDBDBD;
    border: 1.5px solid #E0E0E0;
}
"""

_CARD_STYLE = f"background: {_PANEL_BG}; border: 1px solid #E0E0E0; border-radius: 10px;"


def divider() -> QWidget:
    widget = QWidget()
    widget.setFixedHeight(1)
    widget.setStyleSheet(_DIVIDER_CSS)
    return widget


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(_SECTION_LBL)
    return label


def section_hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(_SECTION_HINT)
    return label

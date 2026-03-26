from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QWidget

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    BORDER,
    GHOST_BTN_STYLE,
    PRIMARY,
    PRIMARY_DARK,
    PRIMARY_LIGHT,
    TEXT_COLOR,
)

APP_BG = BG_COLOR
APP_PANEL_BG = "#FFFFFF"
APP_CARD_STYLE = f"background: {APP_PANEL_BG}; border: 1px solid {BORDER}; border-radius: 10px;"
APP_SECTION_LABEL_STYLE = (
    "color: #1A1A2E; font-size: 9pt; font-weight: bold; background: transparent; padding: 4px 0;"
)
APP_SECTION_HINT_STYLE = (
    "color: #666688; font-size: 8.5pt; background: transparent; padding: 0 0 4px 0;"
)
APP_CAPTION_STYLE = "color: #888899; font-size: 8pt; background: transparent; padding: 2px 6px;"
APP_LOG_STYLE = f"""
QTextEdit {{
    background: #F3F4F8;
    color: #1A1A2E;
    border: 1px solid {BORDER};
    border-radius: 6px;
    font-family: monospace;
    font-size: 9pt;
    padding: 6px;
}}
"""
APP_PANEL_SPLIT_STYLE = f"background: {APP_PANEL_BG}; border-left: 1px solid {BORDER};"

APP_PRIMARY_BUTTON_STYLE = ACTION_BTN_STYLE
APP_SECONDARY_BUTTON_STYLE = GHOST_BTN_STYLE

APP_SEQUENCE_BUTTON_STYLE = """
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

APP_DANGER_BUTTON_STYLE = """
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

APP_SUCCESS_BUTTON_STYLE = """
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

APP_TOGGLE_OFF_BUTTON_STYLE = """
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

APP_TOGGLE_ON_BUTTON_STYLE = """
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


def panel_style(*, radius: int = 6, bg: str = APP_PANEL_BG, border_color: str = BORDER) -> str:
    return f"background: {bg}; border: 1px solid {border_color}; border-radius: {radius}px;"


def split_panel_style(*, bg: str = APP_PANEL_BG, border_color: str = BORDER) -> str:
    return f"background: {bg}; border-left: 1px solid {border_color};"


def muted_text_style(*, color: str = "#666688", size_pt: float = 9.0, extra: str = "") -> str:
    suffix = f" {extra.strip()}" if extra.strip() else ""
    return f"color: {color}; font-size: {size_pt}pt; background: transparent;{suffix}"


def emphasis_text_style(*, color: str, size_pt: float = 9.0, bold: bool = True, extra: str = "") -> str:
    weight = " font-weight: bold;" if bold else ""
    suffix = f" {extra.strip()}" if extra.strip() else ""
    return f"color: {color}; font-size: {size_pt}pt; background: transparent;{weight}{suffix}"


def monospace_log_style(*, dark: bool = False, font_size_pt: float = 9.0) -> str:
    if dark:
        return f"""
QTextEdit, QPlainTextEdit {{
    background: #1E1E1E;
    color: #D4D4D4;
    font-family: monospace;
    font-size: {font_size_pt}pt;
    border: 1px solid #333;
    border-radius: 4px;
}}
"""
    return f"""
QTextEdit, QPlainTextEdit {{
    background: #F3F4F8;
    color: #1A1A2E;
    border: 1px solid {BORDER};
    border-radius: 6px;
    font-family: monospace;
    font-size: {font_size_pt}pt;
    padding: 6px;
}}
"""


def table_style(*, header_font_pt: float = 9.0, body_font_pt: float = 9.0, radius: int = 6) -> str:
    return f"""
QTableWidget {{
    background: white;
    border: 1px solid {BORDER};
    border-radius: {radius}px;
    gridline-color: #F0F0F0;
    font-size: {body_font_pt}pt;
}}
QHeaderView::section {{
    background: #EDE7F6;
    color: #1A1A2E;
    font-weight: bold;
    font-size: {header_font_pt}pt;
    padding: 5px 4px;
    border: none;
    border-bottom: 1px solid #D0C8E0;
}}
QTableWidget::item:selected {{ background: rgba(144,91,169,0.15); color: #1A1A2E; }}
"""


def list_style(*, radius: int = 4, font_px: int = 12, text_color: str = TEXT_COLOR) -> str:
    return f"""
QListWidget {{
    background: white;
    color: {text_color};
    border: 1px solid {BORDER};
    border-radius: {radius}px;
    font-size: {font_px}px;
}}
QListWidget::item:selected {{ background: #EDE7F6; color: {text_color}; }}
"""


def input_style(*, selector: str = "QLineEdit", radius: int = 6, font_pt: float = 9.0) -> str:
    return f"""
{selector} {{
    background: white;
    color: #1A1A2E;
    border: 1.5px solid {BORDER};
    border-radius: {radius}px;
    padding: 6px 10px;
    font-size: {font_pt}pt;
}}
{selector}:focus {{ border-color: {PRIMARY}; }}
"""


def compact_button_style(
    *,
    variant: str = "primary",
    selector: str = "QPushButton",
    min_height: int = 34,
    radius: int = 6,
) -> str:
    if variant == "primary":
        bg, fg, border, hover, pressed = PRIMARY, "white", PRIMARY, "#7A4D90", "#6B4080"
    elif variant == "secondary":
        bg, fg, border, hover, pressed = "transparent", PRIMARY, PRIMARY, "rgba(144,91,169,0.08)", "rgba(144,91,169,0.12)"
    elif variant == "danger":
        bg, fg, border, hover, pressed = "transparent", "#D32F2F", "#D32F2F", "rgba(211,47,47,0.08)", "rgba(211,47,47,0.12)"
    elif variant == "success":
        bg, fg, border, hover, pressed = "#E8F5E9", "#2E7D32", "#4CAF50", "#DCEDC8", "#C8E6C9"
    else:
        raise ValueError(f"Unsupported button variant: {variant}")

    border_css = f"1.5px solid {border}" if border != "none" else "none"
    return f"""
{selector} {{
    background: {bg};
    color: {fg};
    border: {border_css};
    border-radius: {radius}px;
    font-weight: bold;
    min-height: {min_height}px;
}}
{selector}:hover {{ background: {hover}; }}
{selector}:pressed {{ background: {pressed}; }}
"""


def toggle_button_style(
    *,
    selector: str = "QPushButton",
    radius: int = 4,
    font_pt: float = 9.0,
    checked_bg: str = "#E8F5E9",
    checked_border: str = "#2E7D32",
    checked_fg: str = "#1E4620",
) -> str:
    return f"""
{selector} {{
    background: white;
    color: #1A1A2E;
    border: 1px solid #CFCFCF;
    border-radius: {radius}px;
    font-size: {font_pt}pt;
    padding: 4px 10px;
}}
{selector}:checked {{
    background: {checked_bg};
    border-color: {checked_border};
    color: {checked_fg};
}}
{selector}:hover {{
    background: #F6F6F6;
}}
"""


def semantic_button_style(
    *,
    selector: str = "QPushButton",
    bg: str,
    hover_bg: str,
    fg: str = "white",
    disabled_bg: str = "#9E9E9E",
    disabled_fg: str = "white",
    radius: int = 8,
    min_height: int = 44,
) -> str:
    return f"""
{selector} {{
    background-color: {bg};
    color: {fg};
    border: none;
    border-radius: {radius}px;
    padding: 0 16px;
    font-size: 11pt;
    font-weight: bold;
    min-height: {min_height}px;
}}
{selector}:hover   {{ background-color: {hover_bg}; }}
{selector}:pressed {{ background-color: {hover_bg}; }}
{selector}:disabled {{ background-color: {disabled_bg}; color: {disabled_fg}; }}
"""


def indicator_dot_style(*, color: str, font_pt: int = 18) -> str:
    return f"color: {color}; font-size: {font_pt}px; background: transparent;"


def app_state_label_style(*, fg: str, bg: str) -> str:
    return f"""
    QLabel {{
        color: {fg};
        background: {bg};
        border-bottom: 2px solid {fg};
        font-size: 9pt;
        font-weight: bold;
        letter-spacing: 1px;
        padding: 4px 10px;
    }}
    """


def outlined_role_button_style(*, checked_bg: str = PRIMARY, checked_fg: str = "white") -> str:
    return (
        APP_SECONDARY_BUTTON_STYLE
        + f"""
QPushButton:checked {{
    background-color: {checked_bg};
    color: {checked_fg};
    border-color: {checked_bg};
}}
"""
    )


def divider() -> QWidget:
    widget = QWidget()
    widget.setFixedHeight(1)
    widget.setStyleSheet(f"background: {BORDER};")
    return widget


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(APP_SECTION_LABEL_STYLE)
    return label


def section_hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(APP_SECTION_HINT_STYLE)
    return label

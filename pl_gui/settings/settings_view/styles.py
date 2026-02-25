PRIMARY       = "#905BA9"
PRIMARY_DARK  = "#5B3ED6"
PRIMARY_LIGHT = "rgba(122, 90, 248, 0.10)"
BG_COLOR      = "#F8F9FA"
BORDER        = "#E0E0E0"
TEXT_COLOR    = "#1A1A2E"

###
PRIMARY_HOVER = "#8B6FF9"       # lighter primary for hover
TEXT_PRIMARY = "#1D1B20"     # darker text
TEXT_ON_PRIMARY = "#FFFFFF"
SECONDARY_BG = "#EDE7F6"
SECONDARY_HOVER = "#E0D6F0"
SECONDARY_PRESSED = "#D4CAE4"
TERTIARY_BG = "#F6F7FB"        # same as BG_COLOR
TERTIARY_HOVER = "#EDEEF2"
TERTIARY_PRESSED = "#E5E6EA"
TERTIARY_TEXT = "#7D5260"
DISABLED_BG = "#EDE7F6"
DISABLED_BORDER = "#B0A7BC"
DISABLED_PREVIEW_BG = "#F3EDF7"
DISABLED_PREVIEW_BORDER = "#C4C0CA"
SCROLLBAR_BG = "#F6F7FB"       # same as BG_COLOR
SCROLLBAR_HANDLE = "#CAC4D0"
SCROLLBAR_HANDLE_HOVER = "#79747E"
# Overlay
OVERLAY_BG = "rgba(0, 0, 0, 0.5)"
OVERLAY_LIGHT = "rgba(0, 0, 0, 0.32)"
OVERLAY_SUBTLE = "rgba(0, 0, 0, 0.16)"
OVERLAY_FAINT = "rgba(0, 0, 0, 0.05)"

# Shadows (QColor args as tuples)
SHADOW_LIGHT = (0, 0, 0, 20)
SHADOW_MEDIUM = (0, 0, 0, 30)
SHADOW_DARK = (0, 0, 0, 40)
SHADOW_FAB = (0, 0, 0, 60)
SHADOW_PRIMARY_LIGHT = (122, 90, 248, 30)
SHADOW_PRIMARY = (122, 90, 248, 40)
SHADOW_PRIMARY_HOVER = (122, 90, 248, 60)

TAB_WIDGET_STYLE = f"""
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 0 8px 8px 8px;
    background: {BG_COLOR};
}}
QTabBar::tab {{
    background: white;
    color: #333333;
    border: 2px solid {BORDER};
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    padding: 10px 28px;
    font-size: 11pt;
    font-weight: bold;
    min-width: 100px;
    min-height: 40px;
}}
QTabBar::tab:selected {{
    background: white;
    color: {PRIMARY};
    border-color: {PRIMARY};
    border-bottom: 2px solid white;
}}
QTabBar::tab:hover:!selected {{
    background: {PRIMARY_LIGHT};
}}
"""

GROUP_STYLE = f"""
QGroupBox {{
    color: #333333;
    font-size: 12pt;
    font-weight: bold;
    border: 2px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 10px;
    background: white;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    background: {BG_COLOR};
    border-radius: 4px;
}}
"""

SAVE_BUTTON_STYLE = f"""
QPushButton {{
    background-color: {PRIMARY};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    font-size: 12pt;
    font-weight: bold;
    min-height: 52px;
}}
QPushButton:hover   {{ background-color: {PRIMARY_DARK}; }}
QPushButton:pressed {{ background-color: #4A2EC6; }}
"""

LABEL_STYLE = f"""
QLabel {{
    color: #333333;
    font-size: 11pt;
    font-weight: bold;
    background: transparent;
}}
"""

ACTION_BTN_STYLE = f"""
QPushButton {{
    background-color: {PRIMARY};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0 16px;
    font-size: 11pt;
    font-weight: bold;
    min-height: 44px;
}}
QPushButton:hover   {{ background-color: {PRIMARY_DARK}; }}
QPushButton:pressed {{ background-color: {PRIMARY_DARK}; }}
"""

GHOST_BTN_STYLE = f"""
QPushButton {{
    background-color: white;
    color: {PRIMARY};
    border: 2px solid {PRIMARY};
    border-radius: 8px;
    padding: 0 16px;
    font-size: 11pt;
    font-weight: bold;
    min-height: 44px;
}}
QPushButton:hover   {{ background-color: {PRIMARY_LIGHT}; }}
QPushButton:pressed {{ background-color: {PRIMARY_LIGHT}; }}
"""

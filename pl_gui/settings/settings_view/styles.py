PRIMARY       = "#905BA9"
PRIMARY_DARK  = "#5B3ED6"
PRIMARY_LIGHT = "rgba(122, 90, 248, 0.10)"
BG_COLOR      = "#F8F9FA"
BORDER        = "#E0E0E0"
TEXT_COLOR    = "#1A1A2E"
ERROR_COLOR   = "#C62828"
STATUS_OK     = "#2E7D32"

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
TOUCH_SCROLL_AREA_STYLE = f"""
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {SCROLLBAR_BG};
    width: 24px;
    margin: 0;
    border-radius: 8px;
}}
QScrollBar::handle:vertical {{
    background: {SCROLLBAR_HANDLE};
    min-height: 48px;
    border-radius: 8px;
}}
QScrollBar::handle:vertical:hover {{
    background: {SCROLLBAR_HANDLE_HOVER};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
}}
"""
TOUCH_COMBO_STYLE = f"""
QFrame#touchCombo {{
    background: white;
    border: 2px solid {BORDER};
    border-radius: 10px;
}}
QFrame#touchCombo:hover {{ border-color: {PRIMARY}; }}
QFrame#touchCombo QComboBox {{
    background: transparent;
    color: {TEXT_COLOR};
    border: none;
    padding: 0 12px;
    font-size: 12pt;
    min-height: 48px;
}}
QFrame#touchCombo QComboBox::drop-down {{ width: 0; border: none; }}
QFrame#touchCombo QComboBox::down-arrow {{ image: none; }}
QFrame#touchCombo QPushButton#comboDrop {{
    background: transparent;
    color: {PRIMARY};
    border: none;
    font-size: 17pt;
    font-weight: bold;
}}
QFrame#touchCombo QComboBox QAbstractItemView {{
    background: white;
    color: {TEXT_COLOR};
    selection-background-color: {PRIMARY_LIGHT};
    selection-color: {PRIMARY_DARK};
    font-size: 11pt;
    padding: 8px;
}}
"""
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

SETTINGS_FOOTER_STYLE = f"""
QWidget#settingsFooter {{
    background: white;
    border-top: 1px solid {BORDER};
    border-radius: 12px 12px 0 0;
}}
"""

APP_PAGE_TITLE_STYLE = f"color: {PRIMARY}; font-size: 16pt; font-weight: bold; background: transparent;"
SETTINGS_HEADER_STYLE = APP_PAGE_TITLE_STYLE

APP_PHASE_TAB_STYLE = f"""
QTabBar {{ background: white; border: 1px solid {BORDER}; border-radius: 14px; }}
QTabBar::tab {{ color: {TEXT_COLOR}; background: transparent; border: none;
    padding: 10px 18px; min-height: 28px; font-size: 11pt; font-weight: bold; }}
QTabBar::tab:selected {{ color: white; background: {PRIMARY}; border-radius: 10px; }}
"""

SETTINGS_CARD_FRAME_STYLE = f"""
QFrame#settingsCard {{
    background: white;
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QWidget#settingsCardHeader {{
    background: {SECONDARY_BG};
    border-bottom: 1px solid {BORDER};
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
}}
QWidget#settingsCardContent {{
    background: white;
    border-bottom-left-radius: 14px;
    border-bottom-right-radius: 14px;
}}
QLabel#settingsCardTitle {{
    color: {PRIMARY};
    background: transparent;
    font-size: 10pt;
    font-weight: bold;
}}
QGroupBox#settingsCardBody {{
    background: white;
    border: none;
    margin: 0;
    padding: 0;
}}
"""

SETTINGS_STEP_STYLE = f"""
QPushButton {{
    background: white;
    color: {PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px 10px;
    min-height: 30px;
    min-width: 36px;
}}
QPushButton:checked {{
    background: {PRIMARY};
    color: white;
    border-color: {PRIMARY};
}}
"""

SETTINGS_CARD_BODY_STYLE = f"""
QGroupBox#settingsCardBody {{
    background: white;
    border: none;
    border-radius: 0;
    margin: 0;
    padding: 0;
}}
"""

SETTINGS_FIELD_LABEL_STYLE = f"""
QLabel {{
    color: {PRIMARY};
    font-size: 9pt;
    font-weight: normal;
    background: transparent;
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
QPushButton:disabled {{ background-color: {SECONDARY_BG}; color: {DISABLED_BORDER}; }}
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
QPushButton:disabled {{ color: {DISABLED_BORDER}; border-color: {DISABLED_BORDER}; }}
"""

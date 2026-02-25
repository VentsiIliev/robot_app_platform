"""
Central style configuration for new_widgets
This module provides consistent styling constants and stylesheets
for all widgets in the new_widgets directory.
"""
# ================= COLOR CONSTANTS =================
PRIMARY = "#905BA9"
PRIMARY_DARK = "#6D4ED6"
BORDER = "#E4E6F0"
ICON_COLOR = "#905BA9"
QTA_ICON_COLOR = "#FFFFFF"  # Color to use when creating qtawesome icons for mini previews
BG_COLOR = "#F6F7FB"
TOPBAR_BG = "#F6F7FB"
GROUP_BG = "rgba(122,90,248,0.05)"

# Hover / interaction states
PRIMARY_HOVER = "#8B6FF9"       # lighter primary for hover
SURFACE = "#FFFFFF"             # main surface color
TEXT_PRIMARY = "#1D1B20"        # dark text
TEXT_DISABLED = "#9C9A9E"       # grayed-out text
TEXT_ON_PRIMARY = "#FFFFFF"     # white text on primary buttons

# Secondary button variant
SECONDARY_BG = "#EDE7F6"
SECONDARY_HOVER = "#E0D6F0"
SECONDARY_PRESSED = "#D4CAE4"

# Tertiary button variant
TERTIARY_BG = "#F6F7FB"        # same as BG_COLOR
TERTIARY_HOVER = "#EDEEF2"
TERTIARY_PRESSED = "#E5E6EA"
TERTIARY_TEXT = "#7D5260"

# Disabled/grayed-out states
DISABLED_BG = "#EDE7F6"
DISABLED_BORDER = "#B0A7BC"
DISABLED_PREVIEW_BG = "#F3EDF7"
DISABLED_PREVIEW_BORDER = "#C4C0CA"

# Scrollbar
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
# ================= SIZE CONSTANTS =================
BUTTON_SIZE = 60
ICON_SIZE = 26
# ================= BUTTON STYLES =================
NORMAL_STYLE = f"""
QPushButton {{
    background: white;
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QPushButton:hover {{
    border: 1px solid {PRIMARY};
    background-color: rgba(122,90,248,0.05);
}}
QPushButton:pressed {{
    background-color: rgba(122,90,248,0.10);
}}
"""
PRIMARY_STYLE = f"""
QPushButton {{
    background-color: {PRIMARY};
    border: none;
    border-radius: 12px;
}}
QPushButton:hover {{
    background-color: {PRIMARY_DARK};
}}
"""
ACTIVE_STYLE = f"""
QPushButton {{
    border: 1px solid {PRIMARY};
    background-color: rgba(122,90,248,0.12);
    border-radius: 12px;
}}
"""
# ================= DIALOG STYLES =================
DIALOG_BUTTON_STYLE = f"""
QPushButton {{
    background-color: white;
    color: {ICON_COLOR};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 24px;
}}
QPushButton:hover {{
    border: 1px solid {PRIMARY};
    background-color: rgba(122,90,248,0.05);
}}
QPushButton:pressed {{
    background-color: rgba(122,90,248,0.10);
}}
"""
TAB_WIDGET_STYLE = f"""
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: white;
    border-radius: 8px;
    top: -1px;
}}
QTabBar::tab {{
    background: white;
    color: {ICON_COLOR};
    padding: 12px 20px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
    font-size: 11pt;
}}
QTabBar::tab:selected {{
    background: {PRIMARY};
    color: white;
    border-color: {PRIMARY};
}}
QTabBar::tab:hover:!selected {{
    background-color: rgba(122,90,248,0.08);
}}
QComboBox {{
    background-color: white;
    color: #000000;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 28px;
}}
QComboBox:hover {{
    border: 1px solid {PRIMARY};
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: white;
    color: #000000;
    border: 1px solid {BORDER};
    selection-background-color: rgba(122,90,248,0.15);
    selection-color: {PRIMARY_DARK};
}}
QSpinBox, QDoubleSpinBox {{
    background-color: white;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 28px;
}}
QSpinBox:hover, QDoubleSpinBox:hover {{
    border: 1px solid {PRIMARY};
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {PRIMARY};
}}
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border: 2px solid {BORDER};
    border-radius: 4px;
    background: white;
}}
QCheckBox::indicator:hover {{
    border: 2px solid {PRIMARY};
}}
QCheckBox::indicator:checked {{
    background: {PRIMARY};
    border: 2px solid {PRIMARY};
    image: url(none);
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 18px;
    background: white;
    font-weight: bold;
    color: {PRIMARY_DARK};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    background: white;
}}
"""

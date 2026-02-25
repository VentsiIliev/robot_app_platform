"""
Central style configuration for the dashboard plugin.

Provides consistent styling constants and stylesheets aligned with the
application-wide design system.
"""

# ================= COLOR CONSTANTS =================
PRIMARY = "#7A5AF8"
PRIMARY_DARK = "#6D4ED6"
BORDER = "#E4E6F0"
ICON_COLOR = "#905BA9"
BG_COLOR = "#F6F7FB"
TOPBAR_BG = "#F6F7FB"
GROUP_BG = "rgba(122,90,248,0.05)"

# ================= STATUS COLORS =================
STATUS_UNKNOWN = "#808080"
STATUS_INITIALIZING = "#FFA500"
STATUS_READY = "#28a745"
STATUS_LOW_WEIGHT = "#ffc107"
STATUS_EMPTY = "#dc3545"
STATUS_ERROR = "#d9534f"
STATUS_DISCONNECTED = "#6c757d"
STATUS_WARNING_BG = "#fff3cd"

# ================= METRIC COLORS =================
METRIC_BLUE = "#1976D2"
METRIC_GREEN = "#388E3C"

# ================= TEXT COLORS =================
TEXT_PRIMARY = "#2c3e50"
TEXT_VALUE = "#212121"

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

# ================= DASHBOARD CARD STYLES =================
CARD_STYLE = f"""
GlueMeterCard {{
    background-color: white;
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
"""

CARD_HEADER_STYLE = f"""
QLabel {{
    font-size: 18px;
    font-weight: bold;
    color: white;
    padding: 10px;
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {PRIMARY}, stop:1 {PRIMARY_DARK});
    border-radius: 5px;
}}
"""


INFO_FRAME_STYLE = f"""
QFrame {{
    background-color: transparent;
    border: none;
    border-top: 1px solid {BORDER};
    padding: 5px;
}}
"""

METER_FRAME_STYLE = """
background-color: transparent;
border: none;
padding: 4px 0px;
"""

IMAGE_LABEL_STYLE = f"""
QLabel {{
    background-color: {BG_COLOR};
    border-radius: 6px;
    border: 1px solid {BORDER};
}}
"""

CONTAINER_FRAME_STYLE = f"""
QFrame {{
    background-color: white;
    border-radius: 8px;
    border: 1px solid {BORDER};
}}
"""

SLOT_PLACEHOLDER_STYLE = f"""
QFrame {{
    background-color: {GROUP_BG};
    border: 2px dashed {BORDER};
    border-radius: 12px;
}}
"""

WIZARD_IMAGE_PLACEHOLDER_STYLE = f"""
QLabel {{
    background-color: {BG_COLOR};
    border: 2px dashed {BORDER};
    border-radius: 8px;
}}
"""

WIZARD_WARNING_LABEL_STYLE = f"""
font-size: 12px; padding: 10px; background-color: {STATUS_WARNING_BG}; border-radius: 5px;
"""
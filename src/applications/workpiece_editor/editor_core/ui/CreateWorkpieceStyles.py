from pl_gui.settings.settings_view.styles import (
    BG_COLOR,
    BORDER,
    LABEL_STYLE,
    PRIMARY,
    PRIMARY_DARK,
    PRIMARY_LIGHT,
    TEXT_COLOR,
)


_ACTION_BUTTON_BODY = f"""
background-color: {PRIMARY};
color: white;
border: none;
border-radius: 8px;
padding: 0 16px;
font-size: 11pt;
font-weight: bold;
min-height: 44px;
"""

_GHOST_BUTTON_BODY = f"""
background-color: white;
color: {PRIMARY};
border: 2px solid {PRIMARY};
border-radius: 8px;
padding: 0 16px;
font-size: 11pt;
font-weight: bold;
min-height: 44px;
"""


def getStyles():
    styles = f"""
            CreateWorkpieceForm, QWidget#CreateWorkpieceForm {{
                background-color: {BG_COLOR};
                border-radius: 8px;
                border: 1px solid {BORDER};
            }}

            QFrame#field_container {{
                background: transparent;
                border: none;
            }}

            QLabel#form_title {{
                color: {TEXT_COLOR};
                background: transparent;
                font-size: 14pt;
                font-weight: bold;
            }}

            {LABEL_STYLE}

            QLabel#field_label {{
                color: {TEXT_COLOR};
                background: transparent;
                font-size: 11pt;
                font-weight: bold;
            }}

            QLabel#field_icon {{
                background: transparent;
            }}

            QLineEdit {{
                background: white;
                border: 2px solid {BORDER};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 11pt;
                color: {TEXT_COLOR};
                min-height: 44px;
            }}

            QLineEdit:focus {{
                border: 2px solid {PRIMARY};
                outline: none;
            }}

            QComboBox {{
                background: white;
                border: 2px solid {BORDER};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 11pt;
                color: {TEXT_COLOR};
                min-height: 44px;
            }}
            QComboBox:focus, QComboBox:pressed {{
                border: 2px solid {PRIMARY};
                outline: none;
            }}
            QComboBox:hover, QLineEdit:hover {{
                border: 2px solid {PRIMARY};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 36px;
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 12px;
                height: 12px;
            }}

            QComboBox QAbstractItemView,
            QComboBox QListView,
            QListView {{
                background: white;
                color: {TEXT_COLOR};
                selection-background-color: {PRIMARY_LIGHT};
                selection-color: {TEXT_COLOR};
                outline: none;
                border: 1px solid {BORDER};
            }}

            QComboBox QAbstractItemView::item {{
                padding: 8px 10px;
            }}

            QComboBox QAbstractItemView::item:selected,
            QComboBox QAbstractItemView::item:hover,
            QComboBox QListView::item:selected,
            QComboBox QListView::item:hover {{
                background: {PRIMARY_LIGHT};
                color: {TEXT_COLOR};
            }}

            QPushButton#config_button {{
                {_GHOST_BUTTON_BODY}
            }}
            QPushButton#config_button:hover {{
                background-color: {PRIMARY_LIGHT};
            }}

            QPushButton {{
                {_ACTION_BUTTON_BODY}
            }}
            QPushButton:hover {{
                background-color: {PRIMARY_DARK};
            }}
        """

    return styles

def get_input_field_styles():
    styles = f"""
            background: white;
            border: 2px solid {BORDER};
            border-radius: 8px;
            padding: 0 12px;
            color: {TEXT_COLOR};
            font-size: 11pt;
            min-height: 44px;
        """

    return styles

def get_popup_view_styles():
    styles =     f"""
                QListView {{ background: white; color: {TEXT_COLOR}; border: 1px solid {BORDER}; }}
                QListView::item {{ padding: 8px 10px; }}
                QListView::item:selected, QListView::item:hover {{ background: {PRIMARY_LIGHT}; color: {TEXT_COLOR}; }}
                """

    return styles

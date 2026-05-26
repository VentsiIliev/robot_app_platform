import qtawesome as qta
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

from ..new_widgets.SegmentSettingsWidget import (
    SegmentSettingsWidget, update_default_settings, get_default_settings, get_combo_field_key
)

from .styles import (
    PRIMARY_DARK, BORDER, ICON_COLOR, BG_COLOR,
    DIALOG_BUTTON_STYLE
)


class GlobalSettingsDialog(QDialog):
    def __init__(self, point_manager_widget, glue_type_names, parent=None):
        super().__init__(parent)
        self.point_manager_widget = point_manager_widget
        self.glue_type_names = glue_type_names
        self.setWindowTitle("Global Settings")
        self.setMinimumWidth(600)
        self.setMinimumHeight(700)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_COLOR};
            }}
        """)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        title_label = QLabel("Global Settings - Apply to All Segments")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {PRIMARY_DARK};
                padding: 10px;
                background: white;
                border-radius: 8px;
                border: 1px solid {BORDER};
            }}
        """)
        layout.addWidget(title_label)

        default_settings = get_default_settings()
        combo_key = get_combo_field_key()
        inputKeys = [k for k in default_settings.keys() if k != combo_key]

        glue_type_names = self.glue_type_names
        comboEnums = [[combo_key, glue_type_names]] if combo_key else []

        all_keys = inputKeys + ([combo_key] if combo_key else [])
        self.segment_settings_widget = SegmentSettingsWidget(
            all_keys,
            comboEnums,
            parent=self,
            segment=None,
            global_settings=True,
            pointManagerWidget=self.point_manager_widget
        )

        layout.addWidget(self.segment_settings_widget)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        apply_button = QPushButton(self)
        apply_button.setIcon(qta.icon("fa5s.check-double", color=ICON_COLOR))
        apply_button.setIconSize(QSize(16, 16))
        apply_button.setText(" Apply to All Segments")
        apply_button.setFont(QFont("Arial", 11))
        apply_button.setMinimumHeight(42)
        apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button.setStyleSheet(DIALOG_BUTTON_STYLE)
        apply_button.clicked.connect(self.apply_settings_to_all_segments)

        cancel_button = QPushButton(self)
        cancel_button.setIcon(qta.icon("fa5s.times", color=ICON_COLOR))
        cancel_button.setIconSize(QSize(16, 16))
        cancel_button.setText(" Cancel")
        cancel_button.setFont(QFont("Arial", 11))
        cancel_button.setMinimumHeight(42)
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button.setStyleSheet(DIALOG_BUTTON_STYLE)
        cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(apply_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def apply_settings_to_all_segments(self):
        settings_dict = self.segment_settings_widget.get_global_values()

        update_default_settings(settings_dict)

        if self.point_manager_widget:
            self.point_manager_widget.update_all_segments_settings(settings_dict)

        self.accept()

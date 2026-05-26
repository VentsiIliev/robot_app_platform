

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QSizePolicy, QPushButton, QScrollArea, QTabWidget, QApplication
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QFont
import qtawesome as qta

from ...services.settings_service import SettingsService

import os
from ...persistence.model.SettingsConfig import SettingsConfig

from .styles import (
    PRIMARY, PRIMARY_DARK, ICON_COLOR, BORDER, BG_COLOR,
    DIALOG_BUTTON_STYLE, TAB_WIDGET_STYLE
)
from .touch_widgets import TouchSpinBox


def configure_segment_settings(config: SettingsConfig):
    """Configure segment settings from a SettingsConfig object.
    Must be called before any SegmentSettingsWidget is created."""
    service = SettingsService.get_instance()
    service.configure(config)


def get_combo_field_key():
    """Return the key used for the combo box field (e.g. 'Glue Type')."""
    service = SettingsService.get_instance()
    return service.get_combo_field_key()


class SegmentSettingsWidget(QWidget):
    save_requested = pyqtSignal()

    def __init__(self, keys: list[str], combo_enums: list[list], parent=None,
                 segment=None, global_settings=False, pointManagerWidget=None):
        super().__init__(parent)
        self.parent = parent
        self.segment = segment
        if self.segment is not None:
            self.segmentSettings = self.segment.settings
        else:
            self.segmentSettings = None
        self.global_settings = global_settings
        self.pointManagerWidget = pointManagerWidget

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BG_COLOR};
            }}
        """)

        self.keys = keys
        self.combo_enums = {label: enum for label, enum in combo_enums}
        self.inputs = {}
        self.init_ui()
        self.populate_values()

        try:
            from ...virtualKeyboard.VirtualKeyboard import VirtualKeyboardSingleton
            self.vk = VirtualKeyboardSingleton.getInstance()
            self.vk.shown.connect(self.on_virtual_keyboard_shown)
            self.vk.hidden.connect(self.on_virtual_keyboard_hidden)
        except ImportError:
            self.vk = None

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(24, 24, 24, 24)

        service = SettingsService.get_instance()
        groups = service.get_settings_groups()

        def build_fields_grid(keys):
            """Build a grid layout with input fields for the given keys"""
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("""
                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
            """)

            content_widget = QWidget()
            content_widget.setStyleSheet(f"background-color: {BG_COLOR};")
            scroll.setWidget(content_widget)

            layout = QVBoxLayout(content_widget)
            layout.setSpacing(16)
            layout.setContentsMargins(16, 16, 16, 16)

            grid = QGridLayout()
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(16)

            for idx, key in enumerate(keys):
                # Each cell: label on top, control below (vertical)
                field_widget = QWidget()
                field_widget.setStyleSheet("background: transparent;")
                cell_layout = QVBoxLayout(field_widget)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                cell_layout.setSpacing(6)

                label = QLabel(key)
                label.setStyleSheet(f"""
                    QLabel {{
                        color: {PRIMARY_DARK};
                        font-size: 11pt;
                        font-weight: bold;
                        background: transparent;
                    }}
                """)
                cell_layout.addWidget(label)

                if key in self.combo_enums:
                    combo_box = QComboBox()
                    combo_box.setSizePolicy(
                        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                    )
                    combo_box.setMinimumHeight(56)
                    combo_box.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                    combo_box.setStyleSheet(f"""
                        QComboBox {{
                            background-color: white;
                            color: {PRIMARY_DARK};
                            border: 2px solid {PRIMARY};
                            border-radius: 8px;
                            padding: 8px 16px;
                        }}
                        QComboBox:hover {{
                            border: 2px solid {PRIMARY_DARK};
                            background-color: rgba(122,90,248,0.05);
                        }}
                        QComboBox::drop-down {{
                            border: none;
                            width: 40px;
                        }}
                        QComboBox QAbstractItemView {{
                            background: white;
                            color: #000000;
                            border: 1px solid {PRIMARY};
                            selection-background-color: rgba(122,90,248,0.15);
                            selection-color: {PRIMARY_DARK};
                            padding: 8px;
                            font-size: 12pt;
                        }}
                    """)
                    items_list = self.combo_enums[key]
                    if isinstance(items_list, list):
                        for item in items_list:
                            combo_box.addItem(str(item))
                    else:
                        print(f"ERROR: combo_enums[{key}] should be a list, "
                              f"got {type(items_list)}")
                        combo_box.addItem("Error loading values")

                    combo_box.currentTextChanged.connect(
                        lambda val, k=key: self.on_value_changed(k, val)
                    )
                    cell_layout.addWidget(combo_box)
                    self.inputs[key] = combo_box
                else:
                    spin = TouchSpinBox(
                        min_val=-1e6, max_val=1e6, step=1.0, decimals=2,
                        step_options=[0.01, 0.1, 1, 10],
                    )
                    spin.setSizePolicy(
                        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                    )
                    spin.valueChanged.connect(
                        lambda val, k=key: self.on_value_changed(k, str(val))
                    )
                    cell_layout.addWidget(spin)
                    self.inputs[key] = spin

                row, col = divmod(idx, 2)
                grid.addWidget(field_widget, row, col)

            layout.addLayout(grid)
            layout.addStretch(1)

            return scroll

        # Use tabs if there are multiple groups
        if len(groups) > 1:
            tab_widget = QTabWidget()
            tab_widget.setStyleSheet(TAB_WIDGET_STYLE)

            for group in groups:
                tab = build_fields_grid(group.keys)
                tab_widget.addTab(tab, group.title)

            main_layout.addWidget(tab_widget)
        else:
            # Single group - no tabs needed
            if groups:
                group_widget = build_fields_grid(groups[0].keys)
                main_layout.addWidget(group_widget)

        # Save button at the bottom
        save_btn = QPushButton("Save")
        save_btn.setIcon(qta.icon("fa5s.save", color=ICON_COLOR))
        save_btn.setIconSize(QSize(18, 18))
        save_btn.setFont(QFont("Arial", 12))
        save_btn.setMinimumHeight(52)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(DIALOG_BUTTON_STYLE)
        save_btn.clicked.connect(self.print_values)
        main_layout.addWidget(save_btn)

    def populate_values(self):
        service = SettingsService.get_instance()
        default_settings = service.get_defaults()

        if self.global_settings:
            settings_source = default_settings
        else:
            settings_source = (
                self.segmentSettings
                if self.segmentSettings and self.segmentSettings != {}
                else default_settings
            )

        for key, widget in self.inputs.items():
            value = settings_source.get(key, default_settings.get(key, ""))
            if isinstance(widget, TouchSpinBox):
                try:
                    widget.setValue(
                        float(str(value).replace(",", ""))
                        if str(value).strip() != "" else 0.0
                    )
                except ValueError:
                    widget.setValue(0.0)
            elif isinstance(widget, QComboBox):
                index = widget.findText(str(value))
                if index >= 0:
                    widget.setCurrentIndex(index)

    def refresh_global_values(self):
        """Refresh the widget with current default settings."""
        if self.global_settings:
            self.populate_values()

    def on_value_changed(self, key: str, value: str):
        print(f"[Value Changed] {key}: {value}")

    def print_values(self):
        values = self.get_values()
        print("[All Values]", values)
        self.save_requested.emit()

    def get_values(self) -> dict:
        """Return a dictionary with key: input value or selected combo text."""
        result = {}
        for key, widget in self.inputs.items():
            if isinstance(widget, TouchSpinBox):
                result[key] = widget.value()
            elif isinstance(widget, QComboBox):
                result[key] = widget.currentText()

        if self.segment:
            self.segment.set_settings(result)
            print("segment settings", self.segment.settings)

        return result

    def get_global_values(self) -> dict:
        """Return a dictionary for global settings."""
        result = {}
        for key, widget in self.inputs.items():
            if isinstance(widget, TouchSpinBox):
                result[key] = widget.value()
            elif isinstance(widget, QComboBox):
                result[key] = widget.currentText()
        return result

    def set_values(self, values: dict):
        """Set values from a dict of key: value."""
        for key, val in values.items():
            widget = self.inputs.get(key)
            if isinstance(widget, TouchSpinBox):
                try:
                    widget.setValue(float(str(val).replace(",", "")))
                except ValueError:
                    widget.setValue(0.0)
            elif isinstance(widget, QComboBox):
                index = widget.findText(str(val))
                if index >= 0:
                    widget.setCurrentIndex(index)

    def clear(self):
        """Clear all input fields."""
        for widget in self.inputs.values():
            if isinstance(widget, TouchSpinBox):
                widget.clear()
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)

    def on_virtual_keyboard_shown(self):
        print("vk shown")
        scroll_area: QScrollArea = self.findChild(QScrollArea)
        if not scroll_area:
            return
        focused_widget = self.focusWidget()
        if focused_widget and focused_widget in self.inputs.values():
            scroll_area.ensureWidgetVisible(focused_widget, xMargin=0, yMargin=20)
        else:
            if self.inputs:
                last_widget = list(self.inputs.values())[-1]
                scroll_area.ensureWidgetVisible(last_widget, xMargin=0, yMargin=20)

    def on_virtual_keyboard_hidden(self):
        print("vk hidden")
        scroll_area: QScrollArea = self.findChild(QScrollArea)
        if scroll_area:
            scroll_area.ensureVisible(0, 0)


# Settings file path
SETTINGS_FILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "global_segment_settings.json"
)


def save_settings_to_file(settings: dict):
    """Save settings to a JSON file"""
    service = SettingsService.get_instance()
    service.save_to_file(settings)


def load_settings_from_file():
    """Load settings from JSON file, return empty dict if file doesn't exist"""
    service = SettingsService.get_instance()
    return service.load_from_file()


def initialize_default_settings():
    """Initialize default settings by loading from file if available"""
    service = SettingsService.get_instance()
    service.initialize_default_settings()


def update_default_settings(new_settings: dict):
    """Update the global default settings dictionary and save to file"""
    service = SettingsService.get_instance()
    service.update_defaults(new_settings)


def get_default_settings():
    """Get the current default settings"""
    service = SettingsService.get_instance()
    return service.get_defaults()


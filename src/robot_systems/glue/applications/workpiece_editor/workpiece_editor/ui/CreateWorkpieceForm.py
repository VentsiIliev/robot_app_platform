"""
Generic Form Component

Usage Example:
-------------
from enum import Enum
from workpiece_editor.ui.CreateWorkpieceForm import (
    CreateWorkpieceForm, FormFieldConfig, GenericFormConfig
)

# Define any enums you need
class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

# Create field configurations
fields = [
    FormFieldConfig(
        field_id="name",
        field_type="text",
        label="Name",
        icon_path="/path/to/name_icon.png",
        placeholder="Enter name",
        mandatory=True
    ),
    FormFieldConfig(
        field_id="priority",
        field_type="dropdown",
        label="Priority",
        icon_path="/path/to/priority_icon.png",
        options=list(Priority),
        default_value=Priority.MEDIUM.name
    ),
]

# Create form configuration
form_config = GenericFormConfig(
    form_title="Create Item",
    fields=fields,
    accept_button_icon="/path/to/accept_icon.png",
    cancel_button_icon="/path/to/cancel_icon.png",
    config_file="settings/my_form_config.json",
    data_factory=lambda data: {"item": data}  # Optional transform function
)

# Create and use the form
form = CreateWorkpieceForm(
    parent=parent_widget,
    form_config=form_config,
    showButtons=True
)
form.data_submitted.connect(handle_data)
form.show()
"""

import json
import os
from enum import Enum
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon, QPalette, QColor
from PyQt6.QtWidgets import QFrame, QSizePolicy, QSpacerItem, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, \
    QCheckBox, QWidget, QMessageBox, QDialog, QScrollArea, QStyleFactory, QListView

from .CreateWorkpieceStyles import getStyles
from .CreateWorkpieceStyles import get_input_field_styles
from .CreateWorkpieceStyles import get_popup_view_styles

try:
    from .Drawer import Drawer
except ImportError:
    from PyQt6.QtWidgets import QWidget as Drawer

from PyQt6.QtWidgets import QLineEdit


from contour_editor.models.interfaces import IAdditionalDataForm


class FocusLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)


@dataclass
class FormFieldConfig:
    field_id: str
    field_type: str
    label: str
    icon_path: str
    visible: bool = True
    mandatory: bool = False
    placeholder: str = ""
    options: List[Any] = field(default_factory=list)
    default_value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "field_type": self.field_type,
            "label": self.label,
            "icon_path": self.icon_path,
            "visible": self.visible,
            "mandatory": self.mandatory,
            "placeholder": self.placeholder,
            "options": self.options,
            "default_value": self.default_value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FormFieldConfig':
        return cls(
            field_id=data["field_id"],
            field_type=data["field_type"],
            label=data["label"],
            icon_path=data["icon_path"],
            visible=data.get("visible", True),
            mandatory=data.get("mandatory", False),
            placeholder=data.get("placeholder", ""),
            options=data.get("options", []),
            default_value=data.get("default_value")
        )


@dataclass
class GenericFormConfig:
    form_title: str
    fields: List[FormFieldConfig]
    accept_button_icon: str = ""
    cancel_button_icon: str = ""
    config_file: str = "settings/form_config.json"
    data_factory: Optional[Callable] = None

    def get_field(self, field_id: str) -> Optional[FormFieldConfig]:
        for f in self.fields:
            if f.field_id == field_id:
                return f
        return None

    def get_visible_fields(self) -> List[FormFieldConfig]:
        return [f for f in self.fields if f.visible]


class FormConfigManager:

    def __init__(self, form_config: GenericFormConfig):
        self.form_config = form_config
        self.config_file = form_config.config_file
        self.runtime_config = self.load_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    saved = json.load(f)
                    config = {}
                    for field_id, field_data in saved.items():
                        config[field_id] = field_data
                    return config
            else:
                config = {}
                for field in self.form_config.fields:
                    config[field.field_id] = {
                        "visible": field.visible,
                        "mandatory": field.mandatory
                    }
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
            config = {}
            for field in self.form_config.fields:
                config[field.field_id] = {
                    "visible": field.visible,
                    "mandatory": field.mandatory
                }
            return config

    def save_config(self, config):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            self.runtime_config = config
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get_config(self):
        return self.runtime_config

    def is_field_visible(self, field_id):
        field_id_str = field_id if isinstance(field_id, str) else str(field_id)
        return self.runtime_config.get(field_id_str, {}).get("visible", True)

    def is_field_mandatory(self, field_id):
        field_id_str = field_id if isinstance(field_id, str) else str(field_id)
        return self.runtime_config.get(field_id_str, {}).get("mandatory", False)


class FieldConfigWidget(QWidget):

    def __init__(self, field: FormFieldConfig, field_config, parent=None):
        super().__init__(parent)
        self.field = field
        self.init_ui(field_config)

    def init_ui(self, field_config):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        name_label = QLabel(self.field.label)
        name_label.setMinimumWidth(150)
        layout.addWidget(name_label)

        self.visible_checkbox = QCheckBox("Visible")
        self.visible_checkbox.setChecked(field_config.get("visible", True))
        layout.addWidget(self.visible_checkbox)

        self.mandatory_checkbox = QCheckBox("Mandatory")
        self.mandatory_checkbox.setChecked(field_config.get("mandatory", False))
        layout.addWidget(self.mandatory_checkbox)

        self.visible_checkbox.toggled.connect(self._on_visibility_changed)
        self._on_visibility_changed(self.visible_checkbox.isChecked())

        layout.addStretch()
        self.setLayout(layout)

    def _on_visibility_changed(self, visible):
        self.mandatory_checkbox.setEnabled(visible)
        if not visible:
            self.mandatory_checkbox.setChecked(False)

    def get_config(self):
        return {
            "visible": self.visible_checkbox.isChecked(),
            "mandatory": self.mandatory_checkbox.isChecked()
        }


class FormConfigDialog(QDialog):

    config_changed = pyqtSignal(dict)

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.field_widgets = {}
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Form Configuration")
        self.setModal(True)
        self.resize(500, 600)

        layout = QVBoxLayout()

        title_label = QLabel("Configure Form Fields")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        config = self.config_manager.get_config()
        for field in self.config_manager.form_config.fields:
            field_config = config.get(field.field_id, {"visible": field.visible, "mandatory": field.mandatory})
            field_widget = FieldConfigWidget(field, field_config)
            self.field_widgets[field.field_id] = field_widget
            scroll_layout.addWidget(field_widget)

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        button_layout = QHBoxLayout()

        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_button)

        button_layout.addStretch()

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_config)
        save_button.setDefault(True)
        button_layout.addWidget(save_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def reset_to_defaults(self):
        reply = QMessageBox.question(
            self,
            "Reset Configuration",
            "Are you sure you want to reset all fields to their default configuration?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            for field in self.config_manager.form_config.fields:
                if field.field_id in self.field_widgets:
                    field_widget = self.field_widgets[field.field_id]
                    field_widget.visible_checkbox.setChecked(field.visible)
                    field_widget.mandatory_checkbox.setChecked(field.mandatory)

    def save_config(self):
        new_config = {}
        for field_id, field_widget in self.field_widgets.items():
            new_config[field_id] = field_widget.get_config()

        visible_fields = [name for name, config in new_config.items() if config["visible"]]
        if not visible_fields:
            QMessageBox.warning(
                self,
                "Configuration Error",
                "At least one field must be visible!"
            )
            return

        if self.config_manager.save_config(new_config):
            self.config_changed.emit(new_config)
            QMessageBox.information(
                self,
                "Configuration Saved",
                "Form configuration has been saved successfully!"
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Save Error",
                "Failed to save configuration. Please try again."
            )


class CreateWorkpieceForm(Drawer, QFrame):
    data_submitted = pyqtSignal(dict)

    def __init__(self, parent=None, form_config: GenericFormConfig = None, showButtons=False, callBack=None):
        super().__init__(parent)

        if form_config is None:
            raise ValueError("form_config is required. Pass a GenericFormConfig instance.")

        self._parent = parent
        self.onSubmitCallBack = callBack
        self.form_config = form_config

        self.config_manager = FormConfigManager(form_config)
        self.field_widgets = {}
        self.field_containers = {}

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("CreateWorkpieceForm")
        self.apply_stylesheet()

        self.setWindowTitle(form_config.form_title)
        self.setContentsMargins(0, 0, 0, 0)

        self.settingsLayout = QVBoxLayout()
        self.settingsLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.settingsLayout)

        self.buttons = []
        self.icon_widgets = []

        self.setStyleSheet("background: white;")

        self.add_config_button()
        self.build_form()

        if showButtons:
            button_layout = QHBoxLayout()
            self.add_button("Accept", form_config.accept_button_icon, button_layout)
            self.add_button("Cancel", form_config.cancel_button_icon, button_layout)
            self.settingsLayout.addLayout(button_layout)

    def prefill_form(self, data):
        is_dict = isinstance(data, dict)
        for field_name, widget in self.field_widgets.items():
            if is_dict:
                if field_name not in data:
                    continue
                value = data.get(field_name)
            else:
                if not hasattr(data, field_name):
                    continue
                value = getattr(data, field_name, None)

            if value is None:
                continue

            if hasattr(widget, 'setText'):
                widget.setText(str(value))
            elif hasattr(widget, 'setCurrentText'):
                field_config = self.form_config.get_field(field_name)
                if field_config and field_config.field_type == "dropdown":
                    if isinstance(value, Enum):
                        widget.setCurrentText(value.name)
                    else:
                        widget.setCurrentText(str(value))
                else:
                    widget.setCurrentText(str(value))

    def apply_stylesheet(self):
        styles = getStyles()
        self.setStyleSheet(styles)

    def add_config_button(self):
        """Add configuration button to the form"""
        config_layout = QHBoxLayout()
        config_layout.addStretch()

        config_button = QPushButton("Configure Fields")
        config_button.setMaximumWidth(150)
        config_button.clicked.connect(self.show_config_dialog)
        config_button.setObjectName("config_button")
        # config_layout.addWidget(config_button)
        # Put the config button row inside a small container so it aligns with the rest of the form
        container = QFrame()
        container.setObjectName("field_container")
        container.setFrameShape(QFrame.Shape.NoFrame)
        container.setLayout(config_layout)
        self.settingsLayout.addWidget(container)

    def show_config_dialog(self):
        dialog = FormConfigDialog(self.config_manager, self)
        dialog.config_changed.connect(self.refresh_form)
        dialog.exec()

    def refresh_form(self, new_config):
        for field_id, container in self.field_containers.items():
            is_visible = new_config.get(field_id, {}).get("visible", True)
            container.setVisible(is_visible)

    def build_form(self):
        for field in self.form_config.fields:
            if not self.config_manager.is_field_visible(field.field_id):
                continue

            if field.field_type == "text":
                self.add_input_field(field)
            elif field.field_type == "dropdown":
                self.add_dropdown_field(field)

        spacer = QSpacerItem(0, 150, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.settingsLayout.addItem(spacer)

    def add_input_field(self, field_config: FormFieldConfig):
        container = QFrame()
        container.setObjectName("field_container")
        row_layout = QHBoxLayout(container)
        row_layout.setContentsMargins(8, 6, 8, 6)
        row_layout.setSpacing(12)

        icon_label = self.create_icon_label(field_config.icon_path)
        row_layout.addWidget(icon_label)

        input_field = FocusLineEdit(parent=self._parent)
        input_field.setStyleSheet(get_input_field_styles())
        input_field.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)

        input_field.setPlaceholderText(field_config.placeholder)
        input_field.setMinimumHeight(40)
        input_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        if field_config.default_value:
            input_field.setText(str(field_config.default_value))

        row_layout.addWidget(input_field)
        self.settingsLayout.addWidget(container)

        self.field_widgets[field_config.field_id] = input_field
        self.field_containers[field_config.field_id] = container

    def add_dropdown_field(self, field_config: FormFieldConfig):
        container = QFrame()
        container.setObjectName("field_container")
        row_layout = QHBoxLayout(container)
        row_layout.setContentsMargins(8, 6, 8, 6)
        row_layout.setSpacing(12)

        icon_label = self.create_icon_label(field_config.icon_path)
        row_layout.addWidget(icon_label)

        dropdown = QComboBox()
        dropdown.setMinimumHeight(40)
        dropdown.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        try:
            dropdown.setView(QListView())
            popup_view = dropdown.view()
            pal = popup_view.palette()
            pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.Text, QColor("#000000"))
            popup_view.setPalette(pal)
            popup_view.setStyleSheet(get_popup_view_styles())
            popup_view.setAutoFillBackground(True)
            popup_view.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            popup_view.setUniformItemSizes(True)
            if popup_view.viewport() is not None:
                popup_view.viewport().setAutoFillBackground(True)
        except Exception:
            pass

        dropdown.setEditable(False)
        dropdown.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        if field_config.options:
            for option in field_config.options:
                if isinstance(option, Enum):
                    dropdown.addItem(option.name, option.value)
                else:
                    dropdown.addItem(str(option))

        if field_config.default_value:
            dropdown.setCurrentText(str(field_config.default_value))

        row_layout.addWidget(dropdown)
        self.settingsLayout.addWidget(container)

        self.field_widgets[field_config.field_id] = dropdown
        self.field_containers[field_config.field_id] = container


    def add_button(self, button_type, icon_path, layout):
        """Helper method to add a button with an icon and click functionality"""
        button = QPushButton("")
        button.setIcon(QIcon(icon_path))
        button.setMinimumHeight(50)

        if button_type == "Accept":
            self.submit_button = button
            button.clicked.connect(self.onSubmit)
        else:
            self.cancel_button = button
            button.clicked.connect(self.onCancel)

        self.buttons.append(button)
        layout.addWidget(button)

    def validate_mandatory_fields(self):
        errors = []
        config = self.config_manager.get_config()

        for field_name, field_config in config.items():
            if field_config.get("visible", True) and field_config.get("mandatory", False):
                widget = self.field_widgets.get(field_name)
                if widget:
                    if hasattr(widget, 'text'):
                        if not widget.text().strip():
                            errors.append(field_name.replace("_", " ").title())
                    elif hasattr(widget, 'currentText'):
                        if not widget.currentText().strip():
                            errors.append(field_name.replace("_", " ").title())

        return errors

    def get_data(self) -> Dict[str, Any]:
        data = {}
        config = self.config_manager.get_config()

        for field_name, field_config in config.items():
            if field_config.get("visible", True):
                widget = self.field_widgets.get(field_name)
                if widget:
                    if hasattr(widget, 'text'):
                        data[field_name] = widget.text()
                    elif hasattr(widget, 'currentText'):
                        current_text = widget.currentText()
                        form_field = self.form_config.get_field(field_name)
                        if form_field and form_field.options:
                            if form_field.options and isinstance(form_field.options[0], Enum):
                                for option in form_field.options:
                                    if option.name == current_text:
                                        data[field_name] = option.value
                                        break
                                else:
                                    data[field_name] = current_text
                            else:
                                data[field_name] = current_text
                        else:
                            data[field_name] = current_text

        print(f"[CreateWorkpieceForm] data: {data}")

        return data

    def validate(self) -> Tuple[bool, str]:
        validation_errors = self.validate_mandatory_fields()
        if validation_errors:
            error_msg = "The following mandatory fields are empty:\n" + "\n".join(
                f"• {field}" for field in validation_errors)
            return False, error_msg
        return True, ""

    def clear(self) -> None:
        self.clear_form()

    def onSubmit(self) -> bool:
        is_valid, error_msg = self.validate()
        if not is_valid:
            QMessageBox.warning(
                self,
                "Validation Error",
                error_msg
            )
            return False

        data = self.get_data()

        if self.form_config.data_factory:
            result = self.form_config.data_factory(data)
            self.data_submitted.emit(result if isinstance(result, dict) else data)
        else:
            self.data_submitted.emit(data)

        if self.onSubmitCallBack:
            callback_result = self.onSubmitCallBack(data)
            if isinstance(callback_result, tuple):
                success, msg = callback_result
                if not success:
                    QMessageBox.warning(self, "Submission Error", msg)
                    return False

        self.close()
        return True

    def onCancel(self):
        self.close()

    def create_icon_label(self, icon_path, size=50):
        pixmap = QPixmap(icon_path) if icon_path and os.path.exists(icon_path) else QPixmap()
        label = QLabel()
        label.setPixmap(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation))
        self.icon_widgets.append((label, pixmap))
        return label

    def resizeEvent(self, event):
        """ Handle resizing of the window and icon sizes """
        # super().resizeEvent(event)
        if self._parent is None:
            return
        newWidth = self._parent.width()

        # Resize the icons in the labels
        for label, original_pixmap in self.icon_widgets:
            label.setPixmap(original_pixmap.scaled(int(newWidth * 0.02), int(newWidth * 0.02),
                                                   Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation))

        # Resize the icons in the buttons if they exist
        if hasattr(self, 'submit_button') and self.submit_button:
            button_icon_size = QSize(int(newWidth * 0.05), int(newWidth * 0.05))
            self.submit_button.setIconSize(button_icon_size)

        if hasattr(self, 'cancel_button') and self.cancel_button:
            button_icon_size = QSize(int(newWidth * 0.05), int(newWidth * 0.05))
            self.cancel_button.setIconSize(button_icon_size)

    def set_field_value(self, field_id: str, value: Any):
        if field_id in self.field_widgets:
            widget = self.field_widgets[field_id]
            if hasattr(widget, 'setText'):
                widget.setText(str(value))
            elif hasattr(widget, 'setCurrentText'):
                widget.setCurrentText(str(value))

    def clear_form(self):
        for field_name, widget in self.field_widgets.items():
            if hasattr(widget, 'setText'):
                widget.setText("")
            elif hasattr(widget, 'setCurrentIndex'):
                widget.setCurrentIndex(0)


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet("""
        *:focus { outline: 0; }
        QLineEdit:focus, QComboBox:focus { outline: none; }
    """)
    form = CreateWorkpieceForm()
    form.show()
    sys.exit(app.exec())

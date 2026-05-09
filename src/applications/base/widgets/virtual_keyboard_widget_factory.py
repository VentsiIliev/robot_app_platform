from contour_editor.persistence.providers.widget_provider import IWidgetFactory
from PyQt6.QtWidgets import QDoubleSpinBox, QLineEdit, QSpinBox

from src.applications.base.config.virtual_keyboard_config import (
    ENABLE_CUSTOM_VIRTUAL_KEYBOARD,
)
from src.applications.base.widgets.custom_virtual_keyboard import (
    KeyboardDoubleSpinBox,
    KeyboardLineEdit,
    KeyboardSpinBox,
)


class VirtualKeyboardWidgetFactory(IWidgetFactory):
    """Reusable widget factory with optional virtual keyboard support."""

    def create_double_spinbox(self, parent=None):
        if ENABLE_CUSTOM_VIRTUAL_KEYBOARD:
            return KeyboardDoubleSpinBox(parent)
        return QDoubleSpinBox(parent)

    def create_spinbox(self, parent=None):
        if ENABLE_CUSTOM_VIRTUAL_KEYBOARD:
            return KeyboardSpinBox(parent)
        return QSpinBox(parent)

    def create_lineedit(self, parent=None):
        if ENABLE_CUSTOM_VIRTUAL_KEYBOARD:
            return KeyboardLineEdit(parent)
        return QLineEdit(parent)

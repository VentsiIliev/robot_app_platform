
from contour_editor.persistence.providers.widget_provider import IWidgetFactory


class VirtualKeyboardWidgetFactory(IWidgetFactory):
    """Widget factory that creates widgets with virtual keyboard support"""

    def create_double_spinbox(self, parent=None):
        from frontend.virtualKeyboard.VirtualKeyboard import FocusDoubleSpinBox
        return FocusDoubleSpinBox(parent)

    def create_spinbox(self, parent=None):
        from frontend.virtualKeyboard.VirtualKeyboard import FocusSpinBox
        return FocusSpinBox(parent)

    def create_lineedit(self, parent=None):
        from frontend.virtualKeyboard.VirtualKeyboard import FocusLineEdit
        return FocusLineEdit(parent)


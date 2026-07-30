from typing import Any, Callable, List

from pl_gui.settings.settings_view import widget_factory
from pl_gui.settings.settings_view.schema import SettingField, SettingGroup
from pl_gui.settings.settings_view.styles import BORDER, PRIMARY, TEXT_COLOR
from pl_gui.settings.settings_view.widget_factory import WidgetHandler
from src.applications.base.collapsible_settings_view import CollapsibleSettingsView
from src.applications.base.widgets.custom_virtual_keyboard import (
    KeyboardDoubleSpinBox,
    KeyboardLineEdit,
    KeyboardSpinBox,
)


_KEYBOARD_WIDGET_TYPES = ("line_edit", "spinbox", "double_spinbox")

_INPUT_STYLE = f"""
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: white;
    color: {TEXT_COLOR};
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 12pt;
    min-height: 56px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {PRIMARY};
}}
"""


def _make_keyboard_line_edit(field: SettingField, emit: Callable[[Any], None]) -> KeyboardLineEdit:
    widget = KeyboardLineEdit()
    widget.setStyleSheet(_INPUT_STYLE)
    if field.default is not None:
        widget.setText(str(field.default))
    widget.textChanged.connect(emit)
    return widget


def _make_keyboard_spinbox(field: SettingField, emit: Callable[[Any], None]) -> KeyboardSpinBox:
    widget = KeyboardSpinBox()
    widget.setStyleSheet(_INPUT_STYLE)
    widget.setRange(int(field.min_val), int(field.max_val))
    widget.setSingleStep(max(1, int(field.step)))
    if field.suffix:
        widget.setSuffix(field.suffix)
    if field.default is not None:
        widget.setValue(int(field.default))
    widget.valueChanged.connect(emit)
    return widget


def _make_keyboard_double_spinbox(
    field: SettingField,
    emit: Callable[[Any], None],
) -> KeyboardDoubleSpinBox:
    widget = KeyboardDoubleSpinBox()
    widget.setStyleSheet(_INPUT_STYLE)
    widget.setRange(float(field.min_val), float(field.max_val))
    widget.setSingleStep(float(field.step))
    widget.setDecimals(int(field.decimals))
    if field.suffix:
        widget.setSuffix(field.suffix)
    if field.default is not None:
        widget.setValue(float(field.default))
    widget.valueChanged.connect(emit)
    return widget


def _keyboard_setting_handlers() -> dict[str, WidgetHandler]:
    return {
        "line_edit": WidgetHandler(
            create=_make_keyboard_line_edit,
            get_value=lambda widget: widget.text(),
            set_value=lambda widget, value: widget.setText(str(value)),
        ),
        "spinbox": WidgetHandler(
            create=_make_keyboard_spinbox,
            get_value=lambda widget: widget.value(),
            set_value=lambda widget, value: widget.setValue(int(value)),
        ),
        "double_spinbox": WidgetHandler(
            create=_make_keyboard_double_spinbox,
            get_value=lambda widget: widget.value(),
            set_value=lambda widget, value: widget.setValue(float(value)),
        ),
    }


def install_keyboard_setting_handlers() -> dict[str, WidgetHandler]:
    original = {
        widget_type: widget_factory._REGISTRY[widget_type]
        for widget_type in _KEYBOARD_WIDGET_TYPES
    }
    widget_factory._REGISTRY.update(_keyboard_setting_handlers())
    return original


def restore_setting_handlers(handlers: dict[str, WidgetHandler]) -> None:
    widget_factory._REGISTRY.update(handlers)


def build_with_keyboard_setting_handlers(fn: Callable[[], None]) -> None:
    original = install_keyboard_setting_handlers()
    try:
        fn()
    finally:
        restore_setting_handlers(original)


def install_keyboard_setting_handlers_permanently() -> None:
    widget_factory._REGISTRY["line_edit"] = WidgetHandler(
        create=_make_keyboard_line_edit,
        get_value=lambda widget: widget.text(),
        set_value=lambda widget, value: widget.setText(str(value)),
    )
    widget_factory._REGISTRY["spinbox"] = WidgetHandler(
        create=_make_keyboard_spinbox,
        get_value=lambda widget: widget.value(),
        set_value=lambda widget, value: widget.setValue(int(value)),
    )
    widget_factory._REGISTRY["double_spinbox"] = WidgetHandler(
        create=_make_keyboard_double_spinbox,
        get_value=lambda widget: widget.value(),
        set_value=lambda widget, value: widget.setValue(float(value)),
    )


class KeyboardSettingsView(CollapsibleSettingsView):
    """Collapsible settings view whose editable fields use the shared virtual keyboard."""

    def __init__(self, component_name: str = "KeyboardSettingsView", mapper=None, parent=None):
        super().__init__(component_name=component_name, mapper=mapper, parent=parent)

    def add_tab(self, title: str, groups: List[SettingGroup]) -> None:
        build_with_keyboard_setting_handlers(
            lambda: super(KeyboardSettingsView, self).add_tab(title, groups)
        )

    def add_plain_tab(self, title: str, groups: List[SettingGroup]) -> None:
        super().add_tab(title, groups)

from typing import Any, Callable

from PyQt6.QtCore import QEvent, QObject


class _ClickEventFilter(QObject):
    def __init__(self, callback: Callable[[], None], parent=None):
        super().__init__(parent)
        self._callback = callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self._callback()
            return True
        return False


def install_line_edit_click_action(
    form: Any,
    field_id: str,
    on_click: Callable[[], None],
    *,
    placeholder: str | None = None,
    read_only: bool = True,
) -> bool:
    """
    Best-effort installer for click actions on form line-edit style widgets.

    This intentionally relies only on the common `field_widgets` convention used by
    injected forms instead of a specific form class.
    """
    field_widgets = getattr(form, "field_widgets", None)
    if not isinstance(field_widgets, dict):
        return False
    widget = field_widgets.get(field_id)
    if widget is None:
        return False

    if read_only and hasattr(widget, "setReadOnly"):
        widget.setReadOnly(True)
    if placeholder and hasattr(widget, "setPlaceholderText"):
        widget.setPlaceholderText(placeholder)

    if getattr(widget, "_ce_click_action_installed", False):
        return True

    event_filter = _ClickEventFilter(on_click, widget)
    widget.installEventFilter(event_filter)
    widget._ce_click_action_installed = True
    widget._ce_click_action_filter = event_filter
    return True


def set_form_field_value(form: Any, field_id: str, value: Any) -> bool:
    if hasattr(form, "set_field_value"):
        form.set_field_value(field_id, value)
        return True

    field_widgets = getattr(form, "field_widgets", None)
    if not isinstance(field_widgets, dict):
        return False
    widget = field_widgets.get(field_id)
    if widget is None:
        return False
    if hasattr(widget, "setText"):
        widget.setText("" if value is None else str(value))
        return True
    if hasattr(widget, "setCurrentText"):
        widget.setCurrentText("" if value is None else str(value))
        return True
    return False

"""
Widget factory for GenericSettingGroup.

Each widget type is described by a WidgetHandler that knows:
  - how to create the widget and wire its change signal
  - how to read its current value
  - how to set a value (used by set_values, no signal expected)
  - whether it should span both grid columns (full_width)

Adding a new widget type = add one WidgetHandler to _REGISTRY.
Nothing else needs to change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QComboBox, QLineEdit, QWidget

from src.utils.utils_widgets.SwitchButton import QToggle
from src.utils.utils_widgets.int_list_widget import IntListWidget
from src.settings.settings_view.schema import SettingField
from src.settings.settings_view.styles import BORDER, PRIMARY, PRIMARY_DARK
from src.utils.utils_widgets.touch_spinbox import TouchSpinBox


# ── shared styles ─────────────────────────────────────────────────────────────

_COMBO_STYLE = f"""
QComboBox {{
    background: white;
    color: #333333;
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 12pt;
    min-height: 56px;
}}
QComboBox:hover {{ border-color: {PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 40px; }}
QComboBox QAbstractItemView {{
    background: white;
    color: #333333;
    selection-background-color: rgba(122, 90, 248, 0.12);
    selection-color: {PRIMARY_DARK};
    font-size: 11pt;
    padding: 8px;
}}
"""

_LINE_EDIT_STYLE = f"""
QLineEdit {{
    background: white;
    color: #333333;
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 12pt;
    min-height: 56px;
}}
QLineEdit:focus {{ border-color: {PRIMARY}; }}
"""


# ── WidgetHandler ─────────────────────────────────────────────────────────────

@dataclass
class WidgetHandler:
    """
    All widget-type-specific knowledge in one place.

    create(field, emit)  — builds and returns the widget; must connect the
                           widget's change signal to emit(value).
    get_value(widget)    — returns the widget's current value.
    set_value(widget, v) — sets the widget's value silently (caller blocks signals).
    full_width           — True → widget spans both grid columns.
    """
    create:     Callable[[SettingField, Callable[[Any], None]], QWidget]
    get_value:  Callable[[QWidget], Any]
    set_value:  Callable[[QWidget, Any], None]
    full_width: bool = False


# ── per-type factory functions ────────────────────────────────────────────────

def _make_spinbox(f: SettingField, emit: Callable) -> TouchSpinBox:
    decimals = f.decimals if f.widget_type == "double_spinbox" else 0
    w = TouchSpinBox(
        min_val=f.min_val,
        max_val=f.max_val,
        initial=float(f.default) if f.default is not None else 0.0,
        step=f.step,
        decimals=decimals,
        step_options=f.step_options,
        suffix=f.suffix,
    )
    w.valueChanged.connect(emit)
    return w


def _make_combo(f: SettingField, emit: Callable) -> QComboBox:
    w = QComboBox()
    w.setStyleSheet(_COMBO_STYLE)
    w.setFont(QFont("Arial", 12, QFont.Weight.Bold))
    for choice in (f.choices or []):
        w.addItem(str(choice))
    if f.default is not None:
        idx = w.findText(str(f.default))
        if idx >= 0:
            w.setCurrentIndex(idx)
    w.currentTextChanged.connect(emit)
    return w


def _make_line_edit(f: SettingField, emit: Callable) -> QLineEdit:
    w = QLineEdit()
    w.setStyleSheet(_LINE_EDIT_STYLE)
    if f.default is not None:
        w.setText(str(f.default))
    w.textChanged.connect(emit)
    return w


def _make_int_list(f: SettingField, emit: Callable) -> IntListWidget:
    w = IntListWidget(min_val=int(f.min_val), max_val=int(f.max_val))
    if f.default is not None:
        w.set_ids(str(f.default))
    w.valueChanged.connect(emit)
    return w


def _make_toggle(f: SettingField, emit: Callable) -> QToggle:
    w = QToggle()
    w.setFixedHeight(40)
    if f.default is not None:
        w.setChecked(bool(f.default))
    w.stateChanged.connect(lambda state: emit(bool(state)))
    return w


# ── set_value helpers ─────────────────────────────────────────────────────────

def _combo_set(w: QComboBox, v: Any) -> None:
    idx = w.findText(str(v))
    if idx >= 0:
        w.setCurrentIndex(idx)


# ── registry ──────────────────────────────────────────────────────────────────

_SPINBOX_HANDLER = WidgetHandler(
    create=_make_spinbox,
    get_value=lambda w: w.value(),
    set_value=lambda w, v: w.setValue(float(v)),
)

_REGISTRY: dict[str, WidgetHandler] = {
    "spinbox":        _SPINBOX_HANDLER,
    "double_spinbox": _SPINBOX_HANDLER,
    "combo": WidgetHandler(
        create=_make_combo,
        get_value=lambda w: w.currentText(),
        set_value=_combo_set,
    ),
    "line_edit": WidgetHandler(
        create=_make_line_edit,
        get_value=lambda w: w.text(),
        set_value=lambda w, v: w.setText(str(v)),
    ),
    "int_list": WidgetHandler(
        create=_make_int_list,
        get_value=lambda w: w.get_ids(),
        set_value=lambda w, v: w.set_ids(v),
        full_width=True,
    ),
    "toggle": WidgetHandler(
        create=_make_toggle,
        get_value=lambda w: w.isChecked(),
        set_value=lambda w, v: w.setChecked(bool(v)),
    ),
}


def get_handler(widget_type: str) -> WidgetHandler:
    try:
        return _REGISTRY[widget_type]
    except KeyError:
        raise ValueError(
            f"Unknown widget_type: {widget_type!r}. "
            f"Registered types: {sorted(_REGISTRY)}"
        )

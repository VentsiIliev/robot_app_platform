from __future__ import annotations

from typing import Dict

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.schema import SettingField, SettingGroup
from pl_gui.settings.settings_view.styles import (
    BG_COLOR,
    BORDER,
    GROUP_STYLE,
    LABEL_STYLE,
    PRIMARY,
    PRIMARY_DARK,
    PRIMARY_LIGHT,
    TEXT_COLOR,
)
from src.applications.base.widgets.custom_virtual_keyboard import (
    KeyboardDoubleSpinBox,
    KeyboardSpinBox,
)
from src.applications.robot_settings.view.robot_settings_schema import (
    CAMERA_TCP_OFFSET_GROUP,
    CAMERA_Z_SHIFT_PIXEL_GROUP,
    CAMERA_Z_SHIFT_WORLD_GROUP,
)


_SPINBOX_STYLE = f"""
QAbstractSpinBox {{
    background: white;
    color: {TEXT_COLOR};
    border: 2px solid {BORDER};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 12pt;
    min-height: 56px;
}}
QAbstractSpinBox:focus {{
    border-color: {PRIMARY};
}}
"""

_CARD_STYLE = f"""
QWidget#fieldCard {{
    background: white;
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
"""

_HEADER_STYLE = f"""
QWidget#cameraKeyboardHeader {{
    background: {PRIMARY_LIGHT};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
"""


class _CameraKeyboardFieldCard(QWidget):
    def __init__(self, field: SettingField, editor: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("fieldCard")
        self.setStyleSheet(_CARD_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        label = QLabel(field.label)
        label.setStyleSheet(LABEL_STYLE)

        helper = QLabel(self._build_helper_text(field))
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #6A6D80; font-size: 10pt; background: transparent;")

        layout.addWidget(label)
        layout.addWidget(helper)
        layout.addWidget(editor)

    @staticmethod
    def _build_helper_text(field: SettingField) -> str:
        return (
            f"Range: {field.min_val:g} to {field.max_val:g}{field.suffix}. "
            f"Tap to enter an exact value with the virtual keyboard."
        )


class _CameraKeyboardGroup(QGroupBox):
    value_changed = pyqtSignal(str, object)

    def __init__(self, schema: SettingGroup, parent: QWidget | None = None) -> None:
        super().__init__(schema.title, parent)
        self.setStyleSheet(GROUP_STYLE)
        self._schema = schema
        self._widgets: Dict[str, QWidget] = {}
        self._defaults: Dict[str, int | float] = {}
        self._spinbox_keys: Dict[QSpinBox, str] = {}
        self._double_spinbox_keys: Dict[QDoubleSpinBox, str] = {}
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 16, 12, 12)
        outer.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        column_count = max(1, int(self._schema.columns or 2))
        for idx in range(column_count):
            grid.setColumnStretch(idx, 1)

        row = 0
        col = 0
        for field in self._schema.fields:
            editor = self._create_editor(field)
            self._widgets[field.key] = editor
            card = _CameraKeyboardFieldCard(field, editor)
            grid.addWidget(card, row, col)

            col += 1
            if col == column_count:
                col = 0
                row += 1

        outer.addLayout(grid)

    def _create_editor(self, field: SettingField) -> QWidget:
        if field.widget_type == "spinbox":
            widget = KeyboardSpinBox()
            widget.setRange(int(field.min_val), int(field.max_val))
            widget.setSingleStep(max(1, int(field.step)))
            widget.setValue(int(field.default or 0))
            self._defaults[field.key] = int(field.default or 0)
            self._spinbox_keys[widget] = field.key
            widget.valueChanged.connect(self._on_spinbox_changed)
            return self._configure_spinbox(widget, field)

        if field.widget_type == "double_spinbox":
            widget = KeyboardDoubleSpinBox()
            widget.setRange(float(field.min_val), float(field.max_val))
            widget.setDecimals(int(field.decimals))
            widget.setSingleStep(float(field.step))
            widget.setValue(float(field.default or 0.0))
            self._defaults[field.key] = float(field.default or 0.0)
            self._double_spinbox_keys[widget] = field.key
            widget.valueChanged.connect(self._on_double_spinbox_changed)
            return self._configure_spinbox(widget, field)

        raise ValueError(f"Unsupported widget type for keyboard camera tab: {field.widget_type}")

    def _configure_spinbox(self, widget: QAbstractSpinBox, field: SettingField) -> QWidget:
        widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        widget.setKeyboardTracking(False)
        widget.setAccelerated(True)
        widget.setAlignment(Qt.AlignmentFlag.AlignLeft)
        widget.setStyleSheet(_SPINBOX_STYLE)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        if field.suffix:
            widget.setSuffix(field.suffix)
        return widget

    def _on_spinbox_changed(self, value: int) -> None:
        widget = self.sender()
        if isinstance(widget, QSpinBox) and widget in self._spinbox_keys:
            self.value_changed.emit(self._spinbox_keys[widget], value)

    def _on_double_spinbox_changed(self, value: float) -> None:
        widget = self.sender()
        if isinstance(widget, QDoubleSpinBox) and widget in self._double_spinbox_keys:
            self.value_changed.emit(self._double_spinbox_keys[widget], value)

    def set_values(self, values: dict) -> None:
        for key, widget in self._widgets.items():
            if key not in values:
                continue
            widget.blockSignals(True)
            try:
                if isinstance(widget, QSpinBox):
                    widget.setValue(int(values[key]))
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(values[key]))
            finally:
                widget.blockSignals(False)

    def get_values(self) -> dict:
        result = {}
        for key, widget in self._widgets.items():
            if isinstance(widget, QSpinBox):
                result[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                result[key] = widget.value()
        return result

    def reset_to_defaults(self) -> None:
        self.set_values(self._defaults)


class CameraKeyboardSettingsTab(QWidget):
    value_changed = pyqtSignal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_COLOR};")
        self._groups: list[_CameraKeyboardGroup] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        root.addWidget(scroll)

        content = QWidget()
        content.setStyleSheet(f"background: {BG_COLOR};")
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_summary_band())

        for schema in (
            CAMERA_TCP_OFFSET_GROUP,
            CAMERA_Z_SHIFT_PIXEL_GROUP,
            CAMERA_Z_SHIFT_WORLD_GROUP,
        ):
            group = _CameraKeyboardGroup(schema)
            group.value_changed.connect(self._forward_value_changed)
            self._groups.append(group)
            layout.addWidget(group)

        layout.addStretch()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("cameraKeyboardHeader")
        header.setStyleSheet(_HEADER_STYLE)

        layout = QVBoxLayout(header)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        title = QLabel("Camera Settings")
        title.setStyleSheet(f"color: {PRIMARY_DARK}; font-size: 16pt; font-weight: bold; background: transparent;")

        subtitle = QLabel(
            "Alternative camera calibration tab that keeps the current field structure "
            "but replaces step controls with direct virtual-keyboard entry."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #5F6377; font-size: 10pt; background: transparent;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        return header

    def _build_summary_band(self) -> QWidget:
        band = QWidget()
        layout = QHBoxLayout(band)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self._build_summary_chip("Input Model", "Virtual keyboard only"))
        layout.addWidget(self._build_summary_chip("Precision", "Exact typed values"))
        layout.addWidget(self._build_summary_chip("Reuse", "Drop into a raw settings tab"))
        layout.addStretch()
        return band

    @staticmethod
    def _build_summary_chip(title: str, value: str) -> QWidget:
        chip = QWidget()
        chip.setStyleSheet(
            f"background: white; border: 1px solid {BORDER}; border-radius: 12px;"
        )

        layout = QVBoxLayout(chip)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #6A6D80; font-size: 9pt; font-weight: bold; background: transparent;")
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 11pt; font-weight: bold; background: transparent;")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return chip

    def _forward_value_changed(self, key: str, value: object) -> None:
        self.value_changed.emit(key, value)

    def set_values(self, values: dict) -> None:
        for group in self._groups:
            group.set_values(values)

    def get_values(self) -> dict:
        values: dict = {}
        for group in self._groups:
            values.update(group.get_values())
        return values

    def reset_to_defaults(self) -> None:
        for group in self._groups:
            group.reset_to_defaults()

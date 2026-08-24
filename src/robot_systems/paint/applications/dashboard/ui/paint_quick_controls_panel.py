from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.styles import ACTION_BTN_STYLE, GHOST_BTN_STYLE, GROUP_STYLE
from src.applications.base.widgets.custom_virtual_keyboard import KeyboardDoubleSpinBox


class PaintQuickControlsPanel(QWidget):
    """Touch-oriented paint settings and safe OFF commands for the dashboard."""

    unmatched_paint_settings_requested = pyqtSignal(float, float, float)
    device_off_requested = pyqtSignal(str)
    cable_relief_requested = pyqtSignal()

    def __init__(self, toggle_configs: list, parent=None) -> None:
        super().__init__(parent)
        self._device_states = {item.device_id: False for item in toggle_configs}
        self._off_buttons: dict[str, QPushButton] = {}
        self._step_buttons: list[QPushButton] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self._box = QGroupBox()
        self._box.setStyleSheet(GROUP_STYLE)
        box_layout = QVBoxLayout(self._box)
        box_layout.setContentsMargins(14, 20, 14, 12)
        box_layout.setSpacing(6)

        self._velocity = self._make_field(0.1, 100.0, 1.0, "%")
        self._acceleration = self._make_field(0.1, 100.0, 1.0, "%")
        self._offset = self._make_field(-100.0, 100.0, 0.0, " mm")
        self._velocity_label = QLabel()
        self._acceleration_label = QLabel()
        self._offset_label = QLabel()

        settings_grid = QGridLayout()
        settings_grid.setContentsMargins(0, 0, 0, 0)
        settings_grid.setHorizontalSpacing(10)
        settings_grid.setVerticalSpacing(6)
        self._add_field_row(settings_grid, 0, "velocity", self._velocity_label, self._velocity)
        self._add_field_row(settings_grid, 1, "acceleration", self._acceleration_label, self._acceleration)
        self._add_field_row(settings_grid, 2, "offset", self._offset_label, self._offset)
        settings_grid.setColumnStretch(1, 1)
        box_layout.addLayout(settings_grid)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self._apply = QPushButton()
        self._apply.setStyleSheet(ACTION_BTN_STYLE)
        self._apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply.clicked.connect(self._on_apply)
        action_row.addWidget(self._apply, 1)
        for item in toggle_configs:
            button = QPushButton()
            button.setProperty("device_id", item.device_id)
            button.setProperty("device_label", item.label)
            button.setStyleSheet(GHOST_BTN_STYLE)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(self._on_device_off)
            action_row.addWidget(button, 1)
            self._off_buttons[item.device_id] = button
        box_layout.addLayout(action_row)
        self._cable_relief = QPushButton()
        self._cable_relief.setStyleSheet(GHOST_BTN_STYLE)
        self._cable_relief.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cable_relief.clicked.connect(self._on_cable_relief)
        box_layout.addWidget(self._cable_relief)
        root.addWidget(self._box)
        self.retranslateUi()

    @staticmethod
    def _make_field(minimum: float, maximum: float, value: float, suffix: str) -> KeyboardDoubleSpinBox:
        field = KeyboardDoubleSpinBox()
        field.setRange(minimum, maximum)
        field.setDecimals(1)
        field.setSingleStep(1.0)
        field.setValue(value)
        field.setSuffix(suffix)
        field.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        field.setMinimumHeight(44)
        return field

    def _add_field_row(self, grid, row: int, field_id: str, label: QLabel, field) -> None:
        label.setMinimumWidth(95)
        grid.addWidget(label, row, 0)
        controls = QWidget()
        controls.setStyleSheet("background: transparent;")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        controls_layout.addWidget(self._make_step_button(field_id, -1.0, "−"))
        controls_layout.addWidget(field, 1)
        controls_layout.addWidget(self._make_step_button(field_id, 1.0, "+"))
        grid.addWidget(controls, row, 1)

    def _make_step_button(self, field_id: str, direction: float, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("field_id", field_id)
        button.setProperty("step_direction", direction)
        button.setFixedSize(46, 44)
        button.setStyleSheet(GHOST_BTN_STYLE)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAutoRepeat(True)
        button.setAutoRepeatDelay(400)
        button.setAutoRepeatInterval(50)
        button.clicked.connect(self._on_step)
        self._step_buttons.append(button)
        return button

    def _on_step(self) -> None:
        button = self.sender()
        fields = {"velocity": self._velocity, "acceleration": self._acceleration, "offset": self._offset}
        field = fields.get(str(button.property("field_id")))
        if field is not None:
            field.setValue(
                field.value()
                + float(button.property("step_direction") or 0.0) * field.singleStep()
            )

    def _on_apply(self) -> None:
        self.unmatched_paint_settings_requested.emit(
            self._velocity.value(), self._acceleration.value(), self._offset.value()
        )

    def _on_device_off(self) -> None:
        self.device_off_requested.emit(str(self.sender().property("device_id")))

    def _on_cable_relief(self) -> None:
        self.cable_relief_requested.emit()

    def set_unmatched_paint_settings(self, settings: dict) -> None:
        if not settings:
            self._box.setEnabled(False)
            return
        self._velocity.setValue(float(settings.get("velocity_percent", 10.0)))
        self._acceleration.setValue(float(settings.get("acceleration_percent", 10.0)))
        self._offset.setValue(float(settings.get("offset_mm", 0.0)))
        self._box.setEnabled(True)

    def set_settings_editable(self, editable: bool) -> None:
        for widget in (self._velocity, self._acceleration, self._offset, self._apply, *self._step_buttons):
            widget.setEnabled(editable)

    def set_device_state(self, device_id: str, enabled: bool) -> None:
        self._device_states[device_id] = bool(enabled)
        button = self._off_buttons.get(device_id)
        if button is not None:
            button.setEnabled(bool(enabled))

    def set_device_busy(self, device_id: str, busy: bool) -> None:
        button = self._off_buttons.get(device_id)
        if button is not None:
            button.setEnabled(not busy and self._device_states.get(device_id, False))

    def set_cable_relief_busy(self, busy: bool) -> None:
        self._cable_relief.setEnabled(not busy)

    def retranslateUi(self) -> None:
        self._box.setTitle(self.tr("Quick Paint Controls"))
        self._velocity_label.setText(self.tr("Velocity"))
        self._acceleration_label.setText(self.tr("Acceleration"))
        self._offset_label.setText(self.tr("Press Offset"))
        self._apply.setText(self.tr("Apply"))
        self._cable_relief.setText(self.tr("Relieve Cable (Unwind J6)"))
        for button in self._off_buttons.values():
            button.setText(f"{self.tr(str(button.property('device_label')))} {self.tr('OFF')}")

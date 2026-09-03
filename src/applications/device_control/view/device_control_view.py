from __future__ import annotations
from functools import partial
from typing import List

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLabel, QScrollArea, QTabWidget, QWidget,
)
from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    BORDER,
    GHOST_BTN_STYLE,
    GROUP_STYLE,
    LABEL_STYLE,
    PRIMARY,
    PRIMARY_LIGHT,
    TAB_WIDGET_STYLE,
    TERTIARY_TEXT,
    TEXT_COLOR,
)
from src.applications.base.app_styles import indicator_dot_style

from src.applications.base.i_application_view import IApplicationView
from pl_gui.utils.utils_widgets.SwitchButton import QToggle
from src.applications.device_control.service.i_device_control_service import (
    IDeviceControlDevice,
    MotorEntry,
)

_MUTED     = "#9E9E9E"

_DOT_ON  = indicator_dot_style(color=PRIMARY)
_DOT_OFF = indicator_dot_style(color=TERTIARY_TEXT)
_DOT_NA  = indicator_dot_style(color=_MUTED)

_STATE_STYLE = f"""
QLabel {{
    background: white;
    color: {TEXT_COLOR};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 11pt;
    min-height: 36px;
}}
"""

_STATE_ERROR_STYLE = f"""
QLabel {{
    background: {PRIMARY_LIGHT};
    color: {TEXT_COLOR};
    border: 1px solid {PRIMARY};
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 11pt;
    font-weight: bold;
    min-height: 36px;
}}
"""

_STATIC_DEVICES = [
    ("laser",       "Laser"),
    ("vacuum_pump", "Vacuum Pump"),
    ("generator",   "Generator"),
]


class DeviceControlView(IApplicationView):

    laser_on_requested        = pyqtSignal()
    laser_off_requested       = pyqtSignal()
    vacuum_pump_on_requested  = pyqtSignal()
    vacuum_pump_off_requested = pyqtSignal()
    motor_on_requested        = pyqtSignal(int)   # carries motor address
    motor_off_requested       = pyqtSignal(int)   # carries motor address
    generator_on_requested    = pyqtSignal()
    generator_off_requested   = pyqtSignal()
    device_action_requested   = pyqtSignal(str, str)
    device_enabled_requested = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__("Device Control", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._inner = QWidget()
        self._inner.setStyleSheet(f"background-color: {BG_COLOR};")
        self._device_layout = QVBoxLayout(self._inner)
        self._device_layout.setSpacing(10)
        self._device_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._inner)
        self._legacy_scroll = scroll
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(TAB_WIDGET_STYLE)
        self._tabs.setVisible(False)
        root.addWidget(self._tabs)
        root.addWidget(scroll)

        self._device_tabs: dict[str, QWidget] = {}
        self._device_tab_layouts: dict[str, QVBoxLayout] = {}
        self._device_state_labels: dict[str, QLabel] = {}
        self._device_buttons: dict[str, list[QPushButton]] = {}
        self._device_action_labels: dict[str, QLabel] = {}
        self._device_enabled_toggles: dict[str, QToggle] = {}
        self._vacuum_status_dot: QLabel | None = None
        self._vacuum_status_label: QLabel | None = None

        self._on_btns:    dict[str, QPushButton] = {}
        self._off_btns:   dict[str, QPushButton] = {}
        self._dots:       dict[str, QLabel]      = {}
        self._motor_boxes: dict[str, QGroupBox]  = {}

        _forwarders = {
            "laser":       (self._on_laser_on,       self._on_laser_off),
            "vacuum_pump": (self._on_vacuum_pump_on,  self._on_vacuum_pump_off),
            "generator":   (self._on_generator_on,    self._on_generator_off),
        }
        for key, label in _STATIC_DEVICES:
            self._add_device_row(key, label, _forwarders[key][0], _forwarders[key][1])

        # motor rows added later via setup_motors()
        self._device_layout.addStretch()

    def setup_devices(self, devices: List[IDeviceControlDevice]) -> None:
        while self._tabs.count():
            widget = self._tabs.widget(0)
            self._tabs.removeTab(0)
            widget.deleteLater()
        self._device_tabs.clear()
        self._device_tab_layouts.clear()
        self._device_state_labels.clear()
        self._device_buttons.clear()
        self._device_action_labels.clear()
        self._device_enabled_toggles.clear()
        self._vacuum_status_dot = None
        self._vacuum_status_label = None

        for device in devices:
            page = QWidget()
            page.setStyleSheet(f"background-color: {BG_COLOR};")
            layout = QVBoxLayout(page)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(16)

            heading = QLabel(device.label)
            heading.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 18pt; font-weight: bold; "
                "background: transparent;"
            )
            hint = QLabel(self.tr("Manage availability, inspect state, and run device commands."))
            hint.setStyleSheet(
                f"color: {TERTIARY_TEXT}; font-size: 10pt; background: transparent;"
            )
            layout.addWidget(heading)
            layout.addWidget(hint)

            lifecycle_box = QGroupBox(self.tr("Availability"))
            lifecycle_box.setStyleSheet(GROUP_STYLE)
            lifecycle_layout = QHBoxLayout(lifecycle_box)
            lifecycle_layout.setContentsMargins(16, 12, 16, 12)
            lifecycle_label = QLabel(self.tr("Enabled"))
            lifecycle_label.setStyleSheet(LABEL_STYLE)
            enabled_toggle = QToggle()
            enabled_toggle.setFixedHeight(40)
            enabled_toggle.setProperty("device_key", device.key)
            enabled_toggle.sync_visual_state(device.is_enabled())
            enabled_toggle.stateChanged.connect(self._on_device_enabled_changed)
            lifecycle_layout.addWidget(lifecycle_label)
            lifecycle_layout.addStretch()
            lifecycle_layout.addWidget(enabled_toggle)
            layout.addWidget(lifecycle_box)

            if device.key == "vacuum_sensor":
                status_row = QHBoxLayout()
                status_row.setSpacing(12)
                self._vacuum_status_dot = QLabel("●")
                self._vacuum_status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._vacuum_status_dot.setFixedSize(40, 40)
                self._vacuum_status_dot.setStyleSheet(
                    indicator_dot_style(color=_MUTED, font_pt=30)
                )
                self._vacuum_status_label = QLabel(self.tr("Waiting for sensor reading"))
                self._vacuum_status_label.setStyleSheet(
                    f"color: {TERTIARY_TEXT}; font-size: 13pt; font-weight: bold;"
                )
                status_row.addWidget(self._vacuum_status_dot)
                status_row.addWidget(self._vacuum_status_label)
                status_row.addStretch()
                layout.addLayout(status_row)

            state_box = QGroupBox(self.tr("Device State"))
            state_box.setStyleSheet(GROUP_STYLE)
            state_layout = QVBoxLayout(state_box)
            state_layout.setContentsMargins(16, 16, 16, 16)
            state = QLabel(self.tr("State: not read"))
            state.setWordWrap(True)
            state.setStyleSheet(_STATE_STYLE)
            state_layout.addWidget(state)
            layout.addWidget(state_box)

            action_status = QLabel(self.tr("Ready"))
            action_status.setStyleSheet(
                f"color: {TERTIARY_TEXT}; font-size: 10pt; font-weight: bold;"
            )
            buttons = []
            actions = device.actions()
            if actions:
                actions_box = QGroupBox(self.tr("Actions"))
                actions_box.setStyleSheet(GROUP_STYLE)
                actions_layout = QVBoxLayout(actions_box)
                actions_layout.setContentsMargins(16, 16, 16, 16)
                actions_layout.setSpacing(12)
                action_row = QHBoxLayout()
                action_row.setSpacing(12)
                for action, label in actions.items():
                    button = QPushButton(label)
                    button.setProperty("device_key", device.key)
                    button.setProperty("action", action)
                    button.setStyleSheet(self._action_button_style(action))
                    button.setMinimumWidth(140)
                    button.setCursor(Qt.CursorShape.PointingHandCursor)
                    button.clicked.connect(self._on_device_action_clicked)
                    action_row.addWidget(button)
                    buttons.append(button)
                action_row.addStretch()
                actions_layout.addLayout(action_row)
                actions_layout.addWidget(action_status)
                layout.addWidget(actions_box)
            layout.addStretch()
            self._tabs.addTab(page, device.label)
            self._device_tabs[device.key] = page
            self._device_tab_layouts[device.key] = layout
            self._device_state_labels[device.key] = state
            self._device_buttons[device.key] = buttons
            if actions:
                self._device_action_labels[device.key] = action_status
            self._device_enabled_toggles[device.key] = enabled_toggle
            self._set_device_buttons_enabled(device.key, device.is_enabled())
            self._set_device_idle_status(device.key)
            self.set_device_state(
                device.key,
                {"enabled": device.is_enabled(), "healthy": None},
            )

        has_devices = bool(devices)
        self._tabs.setVisible(has_devices)
        self._legacy_scroll.setVisible(not has_devices)
        if has_devices:
            self._tabs.setCurrentIndex(0)

    def set_device_panel(self, device_key: str, panel: QWidget) -> None:
        """Add an optional device-specific panel to an existing device tab."""
        layout = self._device_tab_layouts.get(device_key)
        if layout is None:
            panel.deleteLater()
            return
        layout.insertWidget(max(0, layout.count() - 1), panel)

    def set_device_state(self, device_key: str, state: dict[str, object]) -> None:
        label = self._device_state_labels.get(device_key)
        if label is None:
            return
        if state.get("enabled") is False:
            text = self.tr("Disabled")
            label.setStyleSheet(_STATE_STYLE)
        elif state.get("healthy") is False:
            text = f"Communication error: {state.get('error', 'read failed')}"
            label.setStyleSheet(_STATE_ERROR_STYLE)
        else:
            values = ", ".join(
                f"{self._state_label(key)}: "
                f"{'N/A' if key == 'healthy' and value is None else value}"
                for key, value in state.items()
                if key != "error" or value
            )
            text = f"State: {values or 'OK'}"
            label.setStyleSheet(_STATE_STYLE)
        label.setText(text)
        if device_key == "vacuum_sensor":
            self._set_vacuum_sensor_status(state)

    @staticmethod
    def _state_label(key: str) -> str:
        if key == "healthy":
            return "Health"
        return key.replace("_", " ").title()

    def _set_vacuum_sensor_status(self, state: dict[str, object]) -> None:
        if self._vacuum_status_dot is None or self._vacuum_status_label is None:
            return
        if state.get("healthy") is False:
            color = _MUTED
            text = self.tr("Sensor unavailable")
        elif bool(state.get("detected")):
            color = PRIMARY
            text = self.tr("Workpiece attached")
        else:
            color = TERTIARY_TEXT
            text = self.tr("No workpiece attached")
        self._vacuum_status_dot.setStyleSheet(
            indicator_dot_style(color=color, font_pt=30)
        )
        self._vacuum_status_label.setText(text)
        self._vacuum_status_label.setStyleSheet(
            f"color: {color}; font-size: 14pt; font-weight: bold;"
        )

    def _on_device_action_clicked(self) -> None:
        button = self.sender()
        if isinstance(button, QPushButton):
            self.device_action_requested.emit(
                str(button.property("device_key")),
                str(button.property("action")),
            )

    def _on_device_enabled_changed(self, state: int) -> None:
        toggle = self.sender()
        if isinstance(toggle, QToggle):
            self.device_enabled_requested.emit(
                str(toggle.property("device_key")),
                bool(state),
            )

    @staticmethod
    def _action_button_style(action: str) -> str:
        normalized = action.lower()
        if normalized.endswith("off") or normalized.startswith("close"):
            return GHOST_BTN_STYLE
        return ACTION_BTN_STYLE

    def set_device_busy(self, device_key: str, busy: bool) -> None:
        for button in self._device_buttons.get(device_key, []):
            button.setEnabled(not busy)
        label = self._device_action_labels.get(device_key)
        if label is not None:
            if busy:
                label.setText(self.tr("Working…"))
            else:
                self._set_device_idle_status(device_key)
            label.setStyleSheet(
                f"color: {TERTIARY_TEXT}; font-size: 10pt; font-weight: bold;"
            )

    def set_device_enabled(self, device_key: str, enabled: bool) -> None:
        toggle = self._device_enabled_toggles.get(device_key)
        if toggle is not None:
            blocked = toggle.blockSignals(True)
            try:
                toggle.sync_visual_state(enabled)
            finally:
                toggle.blockSignals(blocked)
        self._set_device_buttons_enabled(device_key, enabled)
        self._set_device_idle_status(device_key)

    def _set_device_buttons_enabled(self, device_key: str, enabled: bool) -> None:
        for button in self._device_buttons.get(device_key, []):
            button.setEnabled(enabled)

    def _set_device_idle_status(self, device_key: str) -> None:
        label = self._device_action_labels.get(device_key)
        toggle = self._device_enabled_toggles.get(device_key)
        if label is None or toggle is None:
            return
        label.setText(self.tr("Ready") if toggle.isChecked() else self.tr("Disabled"))
        label.setStyleSheet(
            f"color: {TERTIARY_TEXT}; font-size: 10pt; font-weight: bold;"
        )

    def set_device_action_result(self, device_key: str, success: bool) -> None:
        label = self._device_action_labels.get(device_key)
        if label is None:
            return
        toggle = self._device_enabled_toggles.get(device_key)
        if success and toggle is not None and not toggle.isChecked():
            label.setText(self.tr("Disabled"))
        else:
            label.setText(self.tr("Command completed") if success else self.tr("Command failed"))
        label.setStyleSheet(
            f"color: {PRIMARY if success else TERTIARY_TEXT}; "
            "font-size: 10pt; font-weight: bold;"
        )

    # ── Motor rows built dynamically from config ───────────────────────

    def setup_motors(self, motors: List[MotorEntry]) -> None:
        for key, box in list(self._motor_boxes.items()):
            self._device_layout.removeWidget(box)
            box.deleteLater()
            self._on_btns.pop(key, None)
            self._off_btns.pop(key, None)
            self._dots.pop(key, None)
        self._motor_boxes.clear()

        for motor in motors:
            key = f"motor_{motor.address}"
            self._add_device_row(
                key, motor.name,
                partial(self._emit_motor_on,  motor.address),
                partial(self._emit_motor_off, motor.address),
            )


    def _add_device_row(self, key: str, label: str, on_slot, off_slot) -> None:
        box = QGroupBox(label)
        box.setStyleSheet(GROUP_STYLE)
        row = QHBoxLayout(box)
        row.setSpacing(12)
        row.setContentsMargins(16, 8, 16, 8)

        dot = QLabel("●")
        dot.setStyleSheet(_DOT_NA)
        dot.setFixedWidth(22)

        btn_on = QPushButton("ON")
        btn_on.setStyleSheet(ACTION_BTN_STYLE)
        btn_on.setEnabled(False)
        btn_on.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_on.clicked.connect(on_slot)

        btn_off = QPushButton("OFF")
        btn_off.setStyleSheet(GHOST_BTN_STYLE)
        btn_off.setEnabled(False)
        btn_off.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_off.clicked.connect(off_slot)

        row.addWidget(dot)
        row.addWidget(btn_on)
        row.addWidget(btn_off)
        row.addStretch()

        self._on_btns[key]  = btn_on
        self._off_btns[key] = btn_off
        self._dots[key]     = dot
        if key.startswith("motor_"):
            self._motor_boxes[key] = box

        # Insert before the trailing stretch
        self._device_layout.insertWidget(self._device_layout.count() - 1, box)

    # ── Named forwarders — static devices ─────────────────────────────

    def _on_laser_on(self):        self.laser_on_requested.emit()
    def _on_laser_off(self):       self.laser_off_requested.emit()
    def _on_vacuum_pump_on(self):  self.vacuum_pump_on_requested.emit()
    def _on_vacuum_pump_off(self): self.vacuum_pump_off_requested.emit()
    def _on_generator_on(self):    self.generator_on_requested.emit()
    def _on_generator_off(self):   self.generator_off_requested.emit()

    # Named forwarders for motor signals (address-carrying)
    def _emit_motor_on(self, address: int) -> None:
        self.motor_on_requested.emit(address)

    def _emit_motor_off(self, address: int) -> None:
        self.motor_off_requested.emit(address)

    # ── Inbound setters ───────────────────────────────────────────────

    def set_device_available(self, key: str, available: bool) -> None:
        if key not in self._on_btns:
            return
        self._on_btns[key].setEnabled(available)
        self._off_btns[key].setEnabled(available)
        self._on_btns[key].setStyleSheet(ACTION_BTN_STYLE)
        self._off_btns[key].setStyleSheet(GHOST_BTN_STYLE)
        self._dots[key].setStyleSheet(_DOT_OFF if available else _DOT_NA)

    def set_motors_available(self, available: bool) -> None:
        for key in [k for k in self._on_btns if k.startswith("motor_")]:
            self.set_device_available(key, available)

    def set_device_active(self, key: str, active: bool) -> None:
        if key in self._dots:
            self._dots[key].setStyleSheet(_DOT_ON if active else _DOT_OFF)

    def clean_up(self) -> None:
        pass

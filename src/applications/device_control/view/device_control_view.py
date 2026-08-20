from __future__ import annotations
from functools import partial
from typing import List

from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLabel, QScrollArea, QTabWidget, QWidget,
)
from pl_gui.settings.settings_view.styles import BG_COLOR, GROUP_STYLE
from src.applications.base.app_styles import indicator_dot_style, semantic_button_style

from src.applications.base.i_application_view import IApplicationView
from src.applications.device_control.service.i_device_control_service import (
    IDeviceControlDevice,
    MotorEntry,
)

_GREEN     = "#2E7D32"
_GREEN_HOV = "#1B5E20"
_RED       = "#C62828"
_RED_HOV   = "#B71C1C"
_MUTED     = "#9E9E9E"

_BTN_ON = semantic_button_style(bg=_GREEN, hover_bg=_GREEN_HOV, disabled_bg=_MUTED)
_BTN_OFF = semantic_button_style(bg=_RED, hover_bg=_RED_HOV, disabled_bg=_MUTED)
_BTN_NA = semantic_button_style(bg=_MUTED, hover_bg=_MUTED, disabled_bg=_MUTED)

_DOT_ON  = indicator_dot_style(color=_GREEN)
_DOT_OFF = indicator_dot_style(color=_RED)
_DOT_NA  = indicator_dot_style(color=_MUTED)

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
    device_state_poll_requested = pyqtSignal()

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
        self._tabs.setVisible(False)
        root.addWidget(self._tabs)
        root.addWidget(scroll)

        self._device_tabs: dict[str, QWidget] = {}
        self._device_state_labels: dict[str, QLabel] = {}
        self._device_buttons: dict[str, list[QPushButton]] = {}
        self._vacuum_status_dot: QLabel | None = None
        self._vacuum_status_label: QLabel | None = None
        self._state_timer = QTimer(self)
        self._state_timer.timeout.connect(self._on_state_timer)

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
        self._device_state_labels.clear()
        self._device_buttons.clear()
        self._vacuum_status_dot = None
        self._vacuum_status_label = None

        for device in devices:
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)

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
                    f"color: {_MUTED}; font-size: 14pt; font-weight: bold;"
                )
                status_row.addWidget(self._vacuum_status_dot)
                status_row.addWidget(self._vacuum_status_label)
                status_row.addStretch()
                layout.addLayout(status_row)

            state = QLabel("State: not read")
            state.setWordWrap(True)
            layout.addWidget(state)
            buttons = []
            for action, label in device.actions().items():
                button = QPushButton(label)
                button.setProperty("device_key", device.key)
                button.setProperty("action", action)
                button.setStyleSheet(_BTN_ON)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(self._on_device_action_clicked)
                layout.addWidget(button)
                buttons.append(button)
            layout.addStretch()
            self._tabs.addTab(page, device.label)
            self._device_tabs[device.key] = page
            self._device_state_labels[device.key] = state
            self._device_buttons[device.key] = buttons

        has_devices = bool(devices)
        self._tabs.setVisible(has_devices)
        self._legacy_scroll.setVisible(not has_devices)
        if has_devices:
            self._state_timer.start(1000)
            self._on_state_timer()
        else:
            self._state_timer.stop()

    def set_device_state(self, device_key: str, state: dict[str, object]) -> None:
        label = self._device_state_labels.get(device_key)
        if label is None:
            return
        if state.get("healthy") is False:
            text = f"Communication error: {state.get('error', 'read failed')}"
            label.setStyleSheet(f"color: {_RED}; font-weight: bold;")
        else:
            values = ", ".join(f"{key}={value}" for key, value in state.items())
            text = f"State: {values or 'OK'}"
            label.setStyleSheet("")
        label.setText(text)
        if device_key == "vacuum_sensor":
            self._set_vacuum_sensor_status(state)

    def _set_vacuum_sensor_status(self, state: dict[str, object]) -> None:
        if self._vacuum_status_dot is None or self._vacuum_status_label is None:
            return
        if state.get("healthy") is False:
            color = _MUTED
            text = self.tr("Sensor unavailable")
        elif bool(state.get("detected")):
            color = _GREEN
            text = self.tr("Workpiece attached")
        else:
            color = _RED
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

    def _on_state_timer(self) -> None:
        self.device_state_poll_requested.emit()

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
        btn_on.setStyleSheet(_BTN_NA)
        btn_on.setEnabled(False)
        btn_on.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_on.clicked.connect(on_slot)

        btn_off = QPushButton("OFF")
        btn_off.setStyleSheet(_BTN_NA)
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
        self._on_btns[key].setStyleSheet(_BTN_ON if available else _BTN_NA)
        self._off_btns[key].setStyleSheet(_BTN_OFF if available else _BTN_NA)
        self._dots[key].setStyleSheet(_DOT_OFF if available else _DOT_NA)

    def set_motors_available(self, available: bool) -> None:
        for key in [k for k in self._on_btns if k.startswith("motor_")]:
            self.set_device_available(key, available)

    def set_device_active(self, key: str, active: bool) -> None:
        if key in self._dots:
            self._dots[key].setStyleSheet(_DOT_ON if active else _DOT_OFF)

    def clean_up(self) -> None:
        self._state_timer.stop()

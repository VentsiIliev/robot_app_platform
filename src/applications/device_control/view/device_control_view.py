from __future__ import annotations
from functools import partial
from typing import List

from PyQt6.QtCore import pyqtSignal, QEvent, Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLabel, QScrollArea, QWidget,
)
from pl_gui.settings.settings_view.styles import BG_COLOR, GROUP_STYLE
from src.applications.base.app_styles import indicator_dot_style, semantic_button_style

from src.applications.base.i_application_view import IApplicationView
from src.applications.device_control.service.i_device_control_service import MotorEntry

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
        root.addWidget(scroll)

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

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass

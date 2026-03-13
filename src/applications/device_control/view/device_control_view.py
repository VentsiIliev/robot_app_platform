from __future__ import annotations
from PyQt6.QtCore import pyqtSignal, QEvent, Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLabel, QScrollArea, QWidget,
)
from pl_gui.settings.settings_view.styles import BG_COLOR, GROUP_STYLE

from src.applications.base.i_application_view import IApplicationView

_GREEN     = "#2E7D32"
_GREEN_HOV = "#1B5E20"
_RED       = "#C62828"
_RED_HOV   = "#B71C1C"
_MUTED     = "#9E9E9E"

_BTN_ON = f"""
    QPushButton {{
        background-color: {_GREEN};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0 16px;
        font-size: 11pt;
        font-weight: bold;
        min-height: 44px;
    }}
    QPushButton:hover   {{ background-color: {_GREEN_HOV}; }}
    QPushButton:pressed {{ background-color: {_GREEN_HOV}; }}
    QPushButton:disabled {{ background-color: {_MUTED}; color: white; }}
"""

_BTN_OFF = f"""
    QPushButton {{
        background-color: {_RED};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0 16px;
        font-size: 11pt;
        font-weight: bold;
        min-height: 44px;
    }}
    QPushButton:hover   {{ background-color: {_RED_HOV}; }}
    QPushButton:pressed {{ background-color: {_RED_HOV}; }}
    QPushButton:disabled {{ background-color: {_MUTED}; color: white; }}
"""

_BTN_NA = f"""
    QPushButton {{
        background-color: {_MUTED};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0 16px;
        font-size: 11pt;
        font-weight: bold;
        min-height: 44px;
    }}
"""

_DOT_ON  = f"color: {_GREEN};  font-size: 18px; background: transparent;"
_DOT_OFF = f"color: {_RED};    font-size: 18px; background: transparent;"
_DOT_NA  = f"color: {_MUTED};  font-size: 18px; background: transparent;"

_DEVICES = [
    ("laser",        "Laser"),
    ("vacuum_pump",  "Vacuum Pump"),
    ("motor",        "Motor  (Glue Pump)"),
    ("generator",    "Generator"),
]


class DeviceControlView(IApplicationView):

    laser_on_requested        = pyqtSignal()
    laser_off_requested       = pyqtSignal()
    vacuum_pump_on_requested  = pyqtSignal()
    vacuum_pump_off_requested = pyqtSignal()
    motor_on_requested        = pyqtSignal()
    motor_off_requested       = pyqtSignal()
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
        inner = QWidget()
        inner.setStyleSheet(f"background-color: {BG_COLOR};")
        layout = QVBoxLayout(inner)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(inner)
        root.addWidget(scroll)

        self._on_btns:  dict[str, QPushButton] = {}
        self._off_btns: dict[str, QPushButton] = {}
        self._dots:     dict[str, QLabel]      = {}

        _forwarders = {
            "laser":       (self._on_laser_on,       self._on_laser_off),
            "vacuum_pump": (self._on_vacuum_pump_on,  self._on_vacuum_pump_off),
            "motor":       (self._on_motor_on,        self._on_motor_off),
            "generator":   (self._on_generator_on,    self._on_generator_off),
        }

        for key, label in _DEVICES:
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
            btn_on.clicked.connect(_forwarders[key][0])

            btn_off = QPushButton("OFF")
            btn_off.setStyleSheet(_BTN_NA)
            btn_off.setEnabled(False)
            btn_off.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_off.clicked.connect(_forwarders[key][1])

            row.addWidget(dot)
            row.addWidget(btn_on)
            row.addWidget(btn_off)
            row.addStretch()

            self._on_btns[key]  = btn_on
            self._off_btns[key] = btn_off
            self._dots[key]     = dot

            layout.addWidget(box)

        layout.addStretch()

    # ── Named forwarders (no lambdas) ─────────────────────────────────

    def _on_laser_on(self):        self.laser_on_requested.emit()
    def _on_laser_off(self):       self.laser_off_requested.emit()
    def _on_vacuum_pump_on(self):  self.vacuum_pump_on_requested.emit()
    def _on_vacuum_pump_off(self): self.vacuum_pump_off_requested.emit()
    def _on_motor_on(self):        self.motor_on_requested.emit()
    def _on_motor_off(self):       self.motor_off_requested.emit()
    def _on_generator_on(self):    self.generator_on_requested.emit()
    def _on_generator_off(self):   self.generator_off_requested.emit()

    # ── Inbound setters ───────────────────────────────────────────────

    def set_device_available(self, key: str, available: bool) -> None:
        if key not in self._on_btns:
            return
        self._on_btns[key].setEnabled(available)
        self._off_btns[key].setEnabled(available)
        self._on_btns[key].setStyleSheet(_BTN_ON if available else _BTN_NA)
        self._off_btns[key].setStyleSheet(_BTN_OFF if available else _BTN_NA)
        self._dots[key].setStyleSheet(_DOT_OFF if available else _DOT_NA)

    def set_device_active(self, key: str, active: bool) -> None:
        if key in self._dots:
            self._dots[key].setStyleSheet(_DOT_ON if active else _DOT_OFF)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass


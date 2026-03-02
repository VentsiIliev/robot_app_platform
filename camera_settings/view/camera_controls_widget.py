"""
CameraControlsWidget — action controls strip shown below the camera preview.

Every control only emits a signal.  No business logic lives here.
A separate ICameraActionsService (injected via DI) connects to these signals.

Signals
-------
raw_mode_toggled(bool)              — raw/processed mode switched
capture_requested()                 — Capture Image pressed
calibrate_camera_requested()        — Calibrate Camera pressed
calibrate_robot_requested()         — Calibrate Robot pressed
active_area_changed(str)            — user selected an area to edit ("working_area" /
                                      "brightness_area" / "" for none)
"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox
)

from src.plugin.utils_widgets.SwitchButton import QToggle
from src.plugin.utils_widgets.MaterialButton import MaterialButton


_LABEL_DARK = "color: #AAAACC; font-size: 10pt; background: transparent;"

_GROUP_STYLE = """
QGroupBox {
    background: transparent;
    border: none;
}
"""


# Area button colours (match ClickableLabel palette)
_AREA_COLORS = {
    "pickup_area": "#50DC64",   # green
    "spray_area":  "#FF8C32",   # orange
}

_AREA_BTN_BASE = """
QPushButton {{
    background-color: transparent;
    color: {color};
    border: 1.5px solid {color};
    border-radius: 6px;
    padding: 0 10px;
    font-size: 9pt;
    font-weight: bold;
    min-height: 32px;
}}
QPushButton:checked {{
    background-color: {color};
    color: #12121F;
}}
QPushButton:hover:!checked {{ background-color: {color_dim}; }}
"""


def _area_btn_style(color: str) -> str:
    dim = QColor(color)
    dim.setAlpha(50)
    return _AREA_BTN_BASE.format(color=color, color_dim=dim.name(QColor.NameFormat.HexArgb))


class CameraControlsWidget(QWidget):
    """
    Controls strip:
      • Raw Mode toggle
      • Capture Image / Calibrate Camera / Calibrate Robot buttons
      • Working Area / Brightness Area edit-mode toggle buttons

    Usage::

        controls = view.controls
        controls.raw_mode_toggled.connect(service.set_raw_mode)
        controls.capture_requested.connect(service.capture_image)
        controls.calibrate_camera_requested.connect(service.calibrate_camera)
        controls.calibrate_robot_requested.connect(service.calibrate_robot)
        controls.active_area_changed.connect(label.set_active_area)
    """

    raw_mode_toggled           = pyqtSignal(bool)
    capture_requested          = pyqtSignal()
    calibrate_camera_requested = pyqtSignal()
    calibrate_robot_requested  = pyqtSignal()
    active_area_changed        = pyqtSignal(str)   # "" = no area selected
    view_mode_changed          = pyqtSignal(str)   # "live" | "threshold"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #1A1A2E;")
        self._area_btns: dict[str, QPushButton] = {}
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        layout.addWidget(self._build_raw_mode_row())
        layout.addWidget(self._build_threshold_view_row())
        layout.addWidget(self._action_btn("Capture Image",    self.capture_requested))
        layout.addWidget(self._action_btn("Calibrate Camera", self.calibrate_camera_requested))
        layout.addWidget(self._action_btn("Calibrate Robot",  self.calibrate_robot_requested))
        layout.addWidget(self._build_divider())
        layout.addWidget(self._build_area_row())

    def _build_raw_mode_row(self) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(10)

        lbl = QLabel("Raw Mode")
        lbl.setStyleSheet(_LABEL_DARK)

        self._raw_toggle = QToggle()
        self._raw_toggle.setFixedHeight(20)
        self._raw_toggle.setStyleSheet("QToggle { qproperty-text_color: #CCCCDD; }")
        self._raw_toggle.stateChanged.connect(
            lambda state: self.raw_mode_toggled.emit(bool(state))
        )

        hl.addWidget(lbl)
        hl.addStretch()
        hl.addWidget(self._raw_toggle)
        return row

    def _build_threshold_view_row(self) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(10)

        lbl = QLabel("Threshold View")
        lbl.setStyleSheet(_LABEL_DARK)

        self._threshold_toggle = QToggle()
        self._threshold_toggle.setFixedHeight(20)
        self._threshold_toggle.stateChanged.connect(
            lambda state: self.view_mode_changed.emit("threshold" if state else "live")
        )

        hl.addWidget(lbl)
        hl.addStretch()
        hl.addWidget(self._threshold_toggle)
        return row

    def _build_divider(self) -> QWidget:
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #333355;")
        return line

    def _build_area_row(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(container)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)

        lbl = QLabel("Edit Area")
        lbl.setStyleSheet(_LABEL_DARK)
        vl.addWidget(lbl)

        # Active Area Selection
        area_group = QGroupBox()
        area_group.setStyleSheet(_GROUP_STYLE)
        area_layout = QHBoxLayout(area_group)
        area_layout.setSpacing(12)

        self._pickup_btn = MaterialButton("Pickup Area")
        self._spray_btn = MaterialButton("Spray Area")

        self._pickup_btn.setCheckable(True)
        self._spray_btn.setCheckable(True)
        self._pickup_btn.setChecked(True)

        self._pickup_btn.clicked.connect(self._on_pickup_area_clicked)
        self._spray_btn.clicked.connect(self._on_spray_area_clicked)

        area_layout.addWidget(self._pickup_btn)
        area_layout.addWidget(self._spray_btn)

        vl.addWidget(area_group)
        return container

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_area_btn(self, name: str, checked: bool) -> None:
        # Mutual exclusion: uncheck all others
        for n, btn in self._area_btns.items():
            if n != name:
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
        self.active_area_changed.emit(name if checked else "")

    def _on_pickup_area_clicked(self):
        self._spray_btn.setChecked(False)
        self.active_area_changed.emit("pickup_area")

    def _on_spray_area_clicked(self):
        self._pickup_btn.setChecked(False)
        self.active_area_changed.emit("spray_area")

    # ── Public helpers ─────────────────────────────────────────────────────────

    def set_raw_mode(self, enabled: bool) -> None:
        """Programmatically set the Raw Mode toggle (does NOT emit the signal)."""
        self._raw_toggle.blockSignals(True)
        self._raw_toggle.setChecked(enabled)
        self._raw_toggle.blockSignals(False)

    def set_active_area(self, name: str) -> None:
        """Programmatically highlight the active area button (no signal emitted)."""
        for n, btn in self._area_btns.items():
            btn.blockSignals(True)
            btn.setChecked(n == name)
            btn.blockSignals(False)

    # ── Factory helper ─────────────────────────────────────────────────────────

    @staticmethod
    def _action_btn(label: str, signal: pyqtSignal) -> MaterialButton:
        btn = MaterialButton(label)
        btn.clicked.connect(signal)
        return btn

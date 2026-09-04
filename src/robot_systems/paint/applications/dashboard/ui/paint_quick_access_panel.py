from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QPushButton, QVBoxLayout, QWidget

from pl_gui.settings.settings_view.styles import ACTION_BTN_STYLE, GHOST_BTN_STYLE, GROUP_STYLE


class PaintQuickAccessPanel(QWidget):
    """Always-visible device and drying controls for the expanded dashboard."""

    device_toggle_requested = pyqtSignal(str, bool)
    cable_relief_requested = pyqtSignal()
    drying_mode_requested = pyqtSignal(str)
    new_tray_requested = pyqtSignal()

    def __init__(self, toggle_configs: list, parent=None) -> None:
        super().__init__(parent)
        self._configs = list(toggle_configs)
        self._states = {item.device_id: False for item in self._configs}
        self._buttons: dict[str, QPushButton] = {}
        self._drying_mode = "auto"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._box = QGroupBox()
        self._box.setStyleSheet(GROUP_STYLE)
        self._layout = QVBoxLayout(self._box)
        self._layout.setContentsMargins(12, 20, 12, 12)
        self._layout.setSpacing(10)

        self._drying_mode_button = self._button()
        self._drying_mode_button.clicked.connect(self._on_drying_mode)
        self._layout.addWidget(self._drying_mode_button)
        for config in self._configs:
            button = self._button()
            button.setCheckable(config.device_id != "pump")
            button.setProperty("device_id", config.device_id)
            button.clicked.connect(self._on_device_toggle)
            self._layout.addWidget(button)
            self._buttons[config.device_id] = button
        self._cable_relief = self._button()
        self._cable_relief.clicked.connect(self._on_cable_relief)
        self._layout.addWidget(self._cable_relief)
        self._new_tray = self._button()
        self._new_tray.setStyleSheet(ACTION_BTN_STYLE)
        self._new_tray.clicked.connect(self._on_new_tray)
        self._new_tray.hide()
        self._layout.addWidget(self._new_tray)
        self._layout.addStretch(1)
        root.addWidget(self._box, 1)
        self.retranslateUi()

    @staticmethod
    def _button() -> QPushButton:
        button = QPushButton()
        button.setStyleSheet(GHOST_BTN_STYLE)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _on_drying_mode(self) -> None:
        next_mode = {"auto": "manual", "manual": "demo", "demo": "auto"}
        self.drying_mode_requested.emit(next_mode[self._drying_mode])

    def _on_device_toggle(self, checked: bool) -> None:
        device_id = str(self.sender().property("device_id"))
        self.device_toggle_requested.emit(device_id, False if device_id == "pump" else checked)

    def _on_cable_relief(self) -> None:
        self.cable_relief_requested.emit()

    def _on_new_tray(self) -> None:
        self.new_tray_requested.emit()

    def set_drying_mode(self, mode: str) -> None:
        normalized = str(mode).lower()
        self._drying_mode = normalized if normalized in {"auto", "manual", "demo"} else "auto"
        self._new_tray.setVisible(self._drying_mode == "manual")
        self._render_drying_mode()

    def set_drying_mode_busy(self, busy: bool) -> None:
        self._drying_mode_button.setEnabled(not busy)

    def set_device_state(self, device_id: str, enabled: bool) -> None:
        button = self._buttons.get(device_id)
        if button is None:
            return
        self._states[device_id] = bool(enabled)
        if device_id == "pump":
            self._render_device(device_id)
            return
        button.blockSignals(True)
        button.setChecked(bool(enabled))
        button.blockSignals(False)
        self._render_device(device_id)

    def set_device_busy(self, device_id: str, busy: bool) -> None:
        button = self._buttons.get(device_id)
        if button is not None:
            button.setEnabled(not busy)

    def set_cable_relief_busy(self, busy: bool) -> None:
        self._cable_relief.setEnabled(not busy)

    def set_new_tray_enabled(self, enabled: bool) -> None:
        self._new_tray.setEnabled(enabled)

    def retranslateUi(self) -> None:
        self._box.setTitle(self.tr("Quick Controls"))
        self._cable_relief.setText(self.tr("Relieve Cable"))
        self._new_tray.setText(self.tr("New Tray"))
        self._render_drying_mode()
        for config in self._configs:
            self._render_device(config.device_id)

    def _render_drying_mode(self) -> None:
        text = {
            "auto": self.tr("Auto Dry"),
            "manual": self.tr("Tray Dry"),
            "demo": self.tr("Demo Alternate"),
        }[self._drying_mode]
        self._drying_mode_button.setText(text)

    def _render_device(self, device_id: str) -> None:
        button = self._buttons.get(device_id)
        config = next((item for item in self._configs if item.device_id == device_id), None)
        if button is None or config is None:
            return
        enabled = self._states[device_id]
        if device_id == "pump":
            button.setText(f"{self.tr(config.label)}: {self.tr('OFF')}")
            button.setStyleSheet(GHOST_BTN_STYLE)
            return
        state = self.tr("ON") if enabled else self.tr("OFF")
        button.setText(f"{self.tr(config.label)}: {state}")
        button.setStyleSheet(ACTION_BTN_STYLE if enabled else GHOST_BTN_STYLE)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

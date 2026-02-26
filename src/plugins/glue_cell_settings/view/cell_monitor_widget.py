from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame, QSizePolicy

from pl_gui.settings.settings_view.styles import BG_COLOR, TEXT_COLOR, BORDER


class _MonitorBridge(QObject):
    weight_updated = pyqtSignal(float)
    state_updated  = pyqtSignal(str)


class CellMonitorWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bridge = _MonitorBridge(self)
        self._bridge.weight_updated.connect(self._apply_weight)
        self._bridge.state_updated.connect(self._apply_state)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._indicator = QFrame()
        self._indicator.setFixedSize(14, 14)
        self._indicator.setStyleSheet(
            "QFrame { background-color: #808080; border-radius: 7px; }"
        )
        layout.addWidget(self._indicator)

        self._state_label = QLabel("disconnected")
        self._state_label.setStyleSheet(
            f"QLabel {{ color: {TEXT_COLOR}; font-size: 11pt; font-weight: bold; background: transparent; }}"
        )
        layout.addWidget(self._state_label)

        sep = QLabel("|")
        sep.setStyleSheet(f"QLabel {{ color: {BORDER}; font-size: 11pt; background: transparent; }}")
        layout.addWidget(sep)

        self._weight_label = QLabel("— g")
        self._weight_label.setStyleSheet(
            f"QLabel {{ color: {TEXT_COLOR}; font-size: 11pt; font-weight: bold; background: transparent; }}"
        )
        layout.addWidget(self._weight_label)

        layout.addStretch()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background: transparent;")

    def set_weight(self, value: float) -> None:
        self._bridge.weight_updated.emit(value)

    def set_state(self, state: str) -> None:
        self._bridge.state_updated.emit(state)

    def _apply_weight(self, value: float) -> None:
        self._weight_label.setText(f"{value:.2f} g")

    def _apply_state(self, state: str) -> None:
        self._state_label.setText(state)
        colors = {
            "connected":    "#28a745",
            "connecting":   "#f39c12",
            "disconnected": "#6c757d",
            "error":        "#d9534f",
        }
        color = colors.get(state.lower(), "#808080")
        self._indicator.setStyleSheet(
            f"QFrame {{ background-color: {color}; border-radius: 7px; }}"
        )
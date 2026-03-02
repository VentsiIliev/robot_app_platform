from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from pl_gui.utils.utils_widgets.SwitchButton import QToggle

_LABEL_DARK = "color: #AAAACC; font-size: 10pt; background: transparent;"


class CameraControlsWidget(QWidget):

    raw_mode_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #1A1A2E;")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self._build_raw_mode_row())
        layout.addStretch()

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
        self._raw_toggle.stateChanged.connect(
            lambda state: self.raw_mode_toggled.emit(bool(state))
        )
        hl.addWidget(lbl)
        hl.addStretch()
        hl.addWidget(self._raw_toggle)
        return row

    def set_raw_mode(self, enabled: bool) -> None:
        self._raw_toggle.blockSignals(True)
        self._raw_toggle.setChecked(enabled)
        self._raw_toggle.blockSignals(False)

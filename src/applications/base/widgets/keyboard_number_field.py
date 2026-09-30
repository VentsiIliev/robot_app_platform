from PyQt6.QtCore import QElapsedTimer, QEvent, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton,
)

from pl_gui.settings.settings_view.styles import (
    BORDER, PRIMARY, SECONDARY_BG, TEXT_COLOR,
)
from src.applications.base.widgets.custom_virtual_keyboard import (
    KeyboardDoubleSpinBox, KeyboardSpinBox,
)


_NUMBER_FIELD_STYLE = f"""
QFrame#numberField {{
    background: white;
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QPushButton {{
    background: {SECONDARY_BG};
    color: {PRIMARY};
    border: none;
    border-radius: 0;
    font-size: 18pt;
}}
QPushButton#increase {{ border-left: 1px solid {BORDER}; }}
QPushButton#decrease {{ border-right: 1px solid {BORDER}; }}
QPushButton:pressed {{ background: {PRIMARY}; color: white; }}
QAbstractSpinBox {{
    background: white;
    color: {TEXT_COLOR};
    border: none;
    padding: 0 8px;
    font-size: 13pt;
}}
QLabel {{
    background: {SECONDARY_BG};
    color: {PRIMARY};
    border-left: 1px solid {BORDER};
    padding: 0 8px;
    font-size: 9pt;
}}
"""


class KeyboardNumberField(QFrame):
    """Touch stepper around the shared virtual-keyboard spin box."""

    valueChanged = pyqtSignal(object)

    def __init__(self, *, decimal: bool = False, button_width: int = 50, parent=None):
        super().__init__(parent)
        self.setObjectName("numberField")
        self.setStyleSheet(_NUMBER_FIELD_STYLE)
        self.setFixedHeight(52)

        self._spin = KeyboardDoubleSpinBox() if decimal else KeyboardSpinBox()
        self._spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._spin.setMinimumWidth(0)
        self._spin.setFixedHeight(48)
        self._spin.setStyleSheet(f"""
            QAbstractSpinBox {{
                background: white;
                color: {TEXT_COLOR};
                border: none;
                padding: 0 8px;
                font-size: 13pt;
            }}
        """)
        self._spin.valueChanged.connect(self._on_value_changed)

        self._decrease = QPushButton("−")
        self._decrease.setObjectName("decrease")
        self._increase = QPushButton("+")
        self._increase.setObjectName("increase")
        for button in (self._decrease, self._increase):
            button.setFixedWidth(button_width)
            button.setFixedHeight(48)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.installEventFilter(self)
        self._hold_clock = QElapsedTimer()
        self._hold_timer = QTimer(self)
        self._hold_timer.timeout.connect(self._repeat_step)
        self._hold_direction = 0
        self._decrease.pressed.connect(self._start_decrease)
        self._increase.pressed.connect(self._start_increase)
        self._decrease.released.connect(self._stop_hold)
        self._increase.released.connect(self._stop_hold)

        self._unit = QLabel()
        self._unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._unit.setFixedHeight(48)
        self._unit.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self._decrease)
        layout.addWidget(self._spin, 1)
        layout.addWidget(self._unit)
        layout.addWidget(self._increase)

    def _on_value_changed(self, value) -> None:
        self.valueChanged.emit(value)

    def _start_decrease(self) -> None:
        self._start_hold(-1)

    def _start_increase(self) -> None:
        self._start_hold(1)

    def _start_hold(self, direction: int) -> None:
        self._hold_direction = direction
        self._hold_clock.start()
        self._step_once()
        self._hold_timer.start(400)

    def _repeat_step(self) -> None:
        self._step_once()
        elapsed = self._hold_clock.elapsed()
        interval = 50 if elapsed >= 2400 else 100 if elapsed >= 1200 else 200
        if self._hold_timer.interval() != interval:
            self._hold_timer.setInterval(interval)

    def _step_once(self) -> None:
        if self._hold_direction < 0:
            self._spin.stepDown()
        elif self._hold_direction > 0:
            self._spin.stepUp()

    def _stop_hold(self) -> None:
        self._hold_timer.stop()
        self._hold_direction = 0

    def eventFilter(self, watched, event) -> bool:
        if watched in (self._decrease, self._increase) and event.type() in (
            QEvent.Type.Leave, QEvent.Type.Hide, QEvent.Type.EnabledChange,
        ):
            self._stop_hold()
        return super().eventFilter(watched, event)

    def setRange(self, minimum, maximum) -> None:
        self._spin.setRange(minimum, maximum)

    def setSingleStep(self, step) -> None:
        self._spin.setSingleStep(step)

    def setDecimals(self, decimals: int) -> None:
        self._spin.setDecimals(decimals)

    def setSuffix(self, suffix: str) -> None:
        self._unit.setText(suffix.strip())
        self._unit.setVisible(bool(suffix.strip()))

    def setValue(self, value) -> None:
        self._spin.setValue(value)

    def value(self):
        return self._spin.value()

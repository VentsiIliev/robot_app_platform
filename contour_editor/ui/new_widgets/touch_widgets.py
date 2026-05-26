"""
Shared touch-friendly input widgets for use across new_widgets dialogs.
"""
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QWidget, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont
import qtawesome as qta

from .styles import PRIMARY, PRIMARY_DARK, BORDER, ICON_COLOR


class TouchSpinBox(QFrame):
    """
    Touch-friendly stepper: large – button / value label / + button.

    Parameters
    ----------
    min_val      : lower bound (inclusive)
    max_val      : upper bound (inclusive)
    initial      : starting value (clamped to [min_val, max_val])
    step         : initial increment/decrement per tap (default 1.0)
    decimals     : decimal places shown in the label (0 → integer display)
    suffix       : text appended to the displayed value (e.g. " mm", "°")
    step_options : optional list of step sizes shown as selectable pills
                   e.g. [0.01, 0.1, 1, 10]. When provided a compact row of
                   pills is shown below the stepper so the user can switch
                   precision without extra dialog clutter.
    """

    valueChanged = pyqtSignal(float)

    def __init__(self, min_val, max_val, initial=0.0, step=1.0,
                 decimals=1, suffix="", step_options=None, parent=None):
        super().__init__(parent)
        self._min = float(min_val)
        self._max = float(max_val)
        self._step = float(step)
        self._decimals = decimals
        self._suffix = suffix
        self._value = max(self._min, min(self._max, float(initial)))
        self._step_btns: dict = {}

        has_steps = bool(step_options)
        self.setFixedHeight(128 if has_steps else 72)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # ── Stepper row ────────────────────────────────────────────────
        stepper_row = QWidget()
        stepper_row.setStyleSheet("background: transparent; border: none;")
        stepper_layout = QHBoxLayout(stepper_row)
        stepper_layout.setContentsMargins(0, 0, 0, 0)
        stepper_layout.setSpacing(8)

        _btn_style = f"""
            QPushButton {{
                background: white;
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                border: 1px solid {PRIMARY};
                background-color: rgba(122,90,248,0.05);
            }}
            QPushButton:pressed {{
                background-color: rgba(122,90,248,0.15);
            }}
            QPushButton:disabled {{
                background-color: {BORDER};
                border: 1px solid {BORDER};
            }}
        """

        self.minus_btn = QPushButton()
        self.minus_btn.setIcon(qta.icon("fa5s.minus", color=ICON_COLOR))
        self.minus_btn.setIconSize(QSize(18, 18))
        self.minus_btn.setFixedSize(56, 56)
        self.minus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.minus_btn.setStyleSheet(_btn_style)
        self.minus_btn.clicked.connect(self._decrement)
        stepper_layout.addWidget(self.minus_btn)

        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.value_label.setStyleSheet(
            f"color: {PRIMARY_DARK}; background: transparent; border: none;"
        )
        stepper_layout.addWidget(self.value_label, stretch=1)

        self.plus_btn = QPushButton()
        self.plus_btn.setIcon(qta.icon("fa5s.plus", color=ICON_COLOR))
        self.plus_btn.setIconSize(QSize(18, 18))
        self.plus_btn.setFixedSize(56, 56)
        self.plus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.plus_btn.setStyleSheet(_btn_style)
        self.plus_btn.clicked.connect(self._increment)
        stepper_layout.addWidget(self.plus_btn)

        outer.addWidget(stepper_row)

        # ── Step-size pill row (optional) ──────────────────────────────
        if has_steps:
            step_row = QWidget()
            step_row.setStyleSheet("background: transparent; border: none;")
            step_layout = QHBoxLayout(step_row)
            step_layout.setContentsMargins(0, 0, 0, 0)
            step_layout.setSpacing(6)
            step_layout.addStretch()

            for s in step_options:
                label = self._fmt_step(s)
                btn = QPushButton(label)
                btn.setFixedHeight(44)
                btn.setMinimumWidth(56)
                btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _, sv=s: self._select_step(sv))
                step_layout.addWidget(btn)
                self._step_btns[s] = btn

            step_layout.addStretch()
            outer.addWidget(step_row)
            self._apply_step_styles()

        self._refresh()

    # ------------------------------------------------------------------
    @staticmethod
    def _fmt_step(s: float) -> str:
        """Format a step value compactly: 0.001 → '0.001', 1.0 → '1'."""
        if s == int(s):
            return str(int(s))
        # Strip trailing zeros after decimal
        return f"{s:g}"

    def _select_step(self, step: float):
        self._step = float(step)
        self._apply_step_styles()

    def _apply_step_styles(self):
        selected = f"""
            QPushButton {{
                background-color: {PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 12px;
            }}
        """
        unselected = f"""
            QPushButton {{
                background-color: transparent;
                color: {PRIMARY_DARK};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: rgba(122,90,248,0.08);
                border: 1px solid {PRIMARY};
            }}
        """
        for s, btn in self._step_btns.items():
            btn.setStyleSheet(selected if s == self._step else unselected)

    # ------------------------------------------------------------------
    def _refresh(self):
        if self._decimals == 0:
            text = f"{int(self._value)}{self._suffix}"
        else:
            text = f"{self._value:.{self._decimals}f}{self._suffix}"
        self.value_label.setText(text)
        self.minus_btn.setEnabled(self._value > self._min)
        self.plus_btn.setEnabled(self._value < self._max)

    def _increment(self):
        self._value = min(round(self._value + self._step, 10), self._max)
        self._refresh()
        self.valueChanged.emit(self._value)

    def _decrement(self):
        self._value = max(round(self._value - self._step, 10), self._min)
        self._refresh()
        self.valueChanged.emit(self._value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def value(self) -> float:
        """Return current value as float."""
        return self._value

    def setValue(self, val):
        """Set value, clamped to [min, max]."""
        self._value = max(self._min, min(self._max, float(val)))
        self._refresh()

    def clear(self):
        """Reset to 0 (or min if 0 is below range)."""
        self.setValue(0.0 if self._min <= 0.0 <= self._max else self._min)
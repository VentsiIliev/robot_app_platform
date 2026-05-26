"""
Dialog for setting the length and angle of a line segment
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont
import qtawesome as qta

from .styles import (
    PRIMARY_DARK, BORDER, ICON_COLOR, BG_COLOR,
    DIALOG_BUTTON_STYLE
)
from .touch_widgets import TouchSpinBox


class SetLengthAndAngleDialog(QDialog):
    """Dialog for inputting desired line length and angle"""

    def __init__(self, current_length_mm, current_angle_deg=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Line Properties")
        self.setModal(False)

        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_COLOR};
            }}
        """)

        self.new_length = None
        self.new_angle = None
        self._has_angle = current_angle_deg is not None

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        # Current value info banner
        if self._has_angle:
            info_text = (
                f"Current: {current_length_mm:.2f} mm "
                f"@ {current_angle_deg:.1f}°"
            )
        else:
            info_text = f"Current Length: {current_length_mm:.2f} mm"

        current_label = QLabel(info_text, self)
        current_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        current_label.setStyleSheet(f"""
            QLabel {{
                color: {PRIMARY_DARK};
                padding: 10px;
                background: white;
                border-radius: 8px;
                border: 1px solid {BORDER};
            }}
        """)
        layout.addWidget(current_label)

        # Length stepper
        length_label = QLabel("New Length (mm):", self)
        length_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        length_label.setStyleSheet(f"color: {PRIMARY_DARK};")
        layout.addWidget(length_label)

        self.length_input = TouchSpinBox(
            min_val=1.0,
            max_val=10000.0,
            initial=current_length_mm,
            step=1.0,
            decimals=2,
            suffix=" mm",
            step_options=[0.01, 0.1, 1, 10],
            parent=self,
        )
        layout.addWidget(self.length_input)

        # Angle stepper (only when an angle was provided)
        if self._has_angle:
            angle_label = QLabel("New Angle (degrees):", self)
            angle_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            angle_label.setStyleSheet(f"color: {PRIMARY_DARK};")
            layout.addWidget(angle_label)

            self.angle_input = TouchSpinBox(
                min_val=-360.0,
                max_val=360.0,
                initial=current_angle_deg,
                step=1.0,
                decimals=2,
                suffix="°",
                step_options=[0.1, 1, 5, 10],
                parent=self,
            )
            layout.addWidget(self.angle_input)
        else:
            self.angle_input = None

        # OK / Cancel buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.ok_button = QPushButton(self)
        self.ok_button.setIcon(qta.icon("fa5s.check", color=ICON_COLOR))
        self.ok_button.setIconSize(QSize(18, 18))
        self.ok_button.setText("  OK")
        self.ok_button.setFont(QFont("Arial", 12))
        self.ok_button.setMinimumHeight(52)
        self.ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_button.setStyleSheet(DIALOG_BUTTON_STYLE)
        self.ok_button.clicked.connect(self._on_ok_clicked)

        self.cancel_button = QPushButton(self)
        self.cancel_button.setIcon(qta.icon("fa5s.times", color=ICON_COLOR))
        self.cancel_button.setIconSize(QSize(18, 18))
        self.cancel_button.setText("  Cancel")
        self.cancel_button.setFont(QFont("Arial", 12))
        self.cancel_button.setMinimumHeight(52)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setStyleSheet(DIALOG_BUTTON_STYLE)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setMinimumWidth(500)

    def _on_ok_clicked(self):
        """Read stepper values and accept."""
        length_value = self.length_input.value()
        if length_value <= 0:
            return

        self.new_length = length_value
        self.new_angle = self.angle_input.value() if self.angle_input else None
        self.accept()

    def get_length(self):
        """Get the entered length value"""
        return self.new_length

    def get_angle(self):
        """Get the entered angle value (None if an angle was not shown)"""
        return self.new_angle
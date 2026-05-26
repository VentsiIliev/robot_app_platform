import qtawesome as qta
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QFrame
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

from .styles import (
    ICON_COLOR, BG_COLOR, DIALOG_BUTTON_STYLE, PRIMARY_DARK, PRIMARY, BORDER
)
from .touch_widgets import TouchSpinBox


class _SegmentedControl(QFrame):
    """Touch-friendly segmented button group that replaces QComboBox."""

    def __init__(self, options, parent=None):
        super().__init__(parent)
        self._options = options
        self._selected = options[0] if options else ""
        self._buttons = {}

        self.setFixedHeight(60)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {BORDER};
                border-radius: 10px;
                border: none;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        for option in options:
            btn = QPushButton(option)
            btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            btn.setFixedHeight(52)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, o=option: self._select(o))
            self._buttons[option] = btn
            layout.addWidget(btn)

        self._apply_styles()

    def _select(self, option):
        self._selected = option
        self._apply_styles()

    def _apply_styles(self):
        for option, btn in self._buttons.items():
            if option == self._selected:
                btn.setChecked(True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {PRIMARY};
                        color: white;
                        border-radius: 8px;
                        border: none;
                    }}
                    QPushButton:hover {{
                        background-color: {PRIMARY_DARK};
                    }}
                """)
            else:
                btn.setChecked(False)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {PRIMARY_DARK};
                        border-radius: 8px;
                        border: none;
                    }}
                    QPushButton:hover {{
                        background-color: rgba(122,90,248,0.10);
                    }}
                """)

    def currentText(self):
        return self._selected


class LayerAndValueInputDialog(QDialog):
    def __init__(self, dialog_title, layer_label, input_labels, input_defaults, input_ranges, parent=None, layer_options=None):
        """
        A generic dialog to handle layer selection and value inputs (spacing or shrink offset).

        :param dialog_title: Title of the dialog (e.g., "Spray Pattern Settings")
        :param layer_label: Label for the layer selection (e.g., "Select layer type for zigzag pattern")
        :param input_labels: List of input field labels (e.g., ["Line grid spacing", "Shrink offset"])
        :param input_defaults: List of default values for the inputs (e.g., [20, 0.0])
        :param input_ranges: List of tuples for each input field's range (e.g., [(1, 1000), (0.0, 50.0)])
        :param parent: The parent widget (optional)
        """
        super().__init__(parent)

        self.setWindowTitle(dialog_title)
        self.setMinimumWidth(480)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_COLOR};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Layer selection
        self.layer_label = QLabel(layer_label)
        self.layer_label.setFont(QFont("Arial", 11))
        self.layer_label.setStyleSheet(f"""
            QLabel {{
                color: {PRIMARY_DARK};
                font-weight: bold;
                padding: 4px 0px;
            }}
        """)
        layout.addWidget(self.layer_label)

        self.layer_combo = _SegmentedControl(layer_options or ["Contour", "Fill"])
        layout.addWidget(self.layer_combo)

        # Touch-friendly input fields
        self.input_widgets = []
        for idx, label in enumerate(input_labels):
            input_label = QLabel(label)
            input_label.setFont(QFont("Arial", 11))
            input_label.setStyleSheet(f"""
                QLabel {{
                    color: {PRIMARY_DARK};
                    font-weight: bold;
                    padding: 4px 0px;
                }}
            """)
            layout.addWidget(input_label)

            is_float = isinstance(input_defaults[idx], float)
            step = 0.1 if is_float else 1
            spin = TouchSpinBox(
                min_val=input_ranges[idx][0],
                max_val=input_ranges[idx][1],
                initial=input_defaults[idx],
                step=step,
                decimals=2 if is_float else 0,
                suffix=" mm",
                step_options=[0.01, 0.1, 1, 10] if is_float else [1, 5, 10, 50],
            )
            self.input_widgets.append(spin)
            layout.addWidget(spin)

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
        self.ok_button.clicked.connect(self.accept)

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

    def get_values(self):
        """
        Returns the selected layer and the values from all input fields.
        The return is a tuple (layer, value1, value2, ...).
        """
        values = [self.layer_combo.currentText()]
        for widget in self.input_widgets:
            values.append(widget.value())
        return tuple(values)

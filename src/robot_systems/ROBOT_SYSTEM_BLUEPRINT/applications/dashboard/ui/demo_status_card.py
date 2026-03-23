from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DemoStatusCard(QWidget):
    """Minimal dashboard card compatible with DashboardWidget typed setters."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self._title = QLabel(label)
        self._weight = QLabel("Weight: n/a")
        self._state = QLabel("State: unknown")
        self._glue_type = QLabel("Type: demo")

        layout.addWidget(self._title)
        layout.addWidget(self._weight)
        layout.addWidget(self._state)
        layout.addWidget(self._glue_type)

    def set_weight(self, grams: float) -> None:
        self._weight.setText(f"Weight: {grams:.1f} g")

    def set_state(self, state: str) -> None:
        self._state.setText(f"State: {state}")

    def set_glue_type(self, glue_type: str) -> None:
        self._glue_type.setText(f"Type: {glue_type}")

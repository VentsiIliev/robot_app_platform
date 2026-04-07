from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class WeldingStatusCard(QWidget):

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self._title = QLabel(label)
        self._state = QLabel("State: unknown")

        layout.addWidget(self._title)
        layout.addWidget(self._state)

    def set_state(self, state: str) -> None:
        self._state.setText(f"State: {state}")


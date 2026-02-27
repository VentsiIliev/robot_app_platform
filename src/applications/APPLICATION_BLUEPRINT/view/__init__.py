"""
Step 7 — View.

Extends AppWidget — required by the shell (provides app_closed signal).
Rule: pure Qt only — no services, no model, no business logic.
      Exposes pyqtSignals for every user action.
      Exposes setter methods for every piece of data the controller pushes.
"""
from PyQt6.QtCore import pyqtSignal, QEvent
from PyQt6.QtWidgets import QLabel, QVBoxLayout

from pl_gui.shell.base_app_widget.AppWidget import AppWidget


class MyView(AppWidget):
    """Pure Qt widget — zero knowledge of services or models."""

    # --- Outbound signals (user actions → controller) ---------------------
    save_requested = pyqtSignal(str)   # emits the new value

    def __init__(self, parent=None):
        super().__init__("MyApplication", parent)

    def setup_ui(self) -> None:
        """Override AppWidget.setup_ui() to replace the default placeholder."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Build your actual widgets here.
        self._label = QLabel("Value: —")
        layout.addWidget(self._label)

        # Wire internal widget signals to outbound pyqtSignals here.
        # e.g. self._save_btn.clicked.connect(lambda: self.save_requested.emit(self._input.text()))

    # --- Inbound setters (controller → view) ------------------------------

    def set_value(self, value: str) -> None:
        self._label.setText(f"Value: {value}")

    # --- AppWidget hooks --------------------------------------------------

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        """Called by shell when the app is closed. Stop timers, threads etc."""
        pass

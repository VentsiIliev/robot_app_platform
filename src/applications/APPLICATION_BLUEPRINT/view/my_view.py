from PyQt6.QtCore import pyqtSignal, QEvent
from PyQt6.QtWidgets import QLabel, QVBoxLayout

from src.applications.base.i_application_view import IApplicationView


class MyView(IApplicationView):
    """Pure Qt widget — no services, no model, no business logic."""
    SHOW_JOG_WIDGET = False
    JOG_FRAME_SELECTOR_ENABLED = False

    # Outbound signals — one per user action
    save_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("MyApplication", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # TODO: replace with real widgets
        self._label = QLabel("Value: —")
        layout.addWidget(self._label)

        # TODO: wire internal signals to outbound pyqtSignals
        # self._btn.clicked.connect(self._on_inner_save)

    def _configure_jog_widget(self) -> None:
        """Optional hook: populate frame options when enabling frame selection."""
        pass

    # ── Inbound setters (controller → view) ──────────────────────────────

    def set_value(self, value: str) -> None:
        self._label.setText(f"Value: {value}")

    # ── Inner forwarders — use named methods, never lambdas or .emit refs ─

    def _on_inner_save(self, value: str) -> None:
        self.save_requested.emit(value)

    # ── AppWidget hooks ───────────────────────────────────────────────────

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass

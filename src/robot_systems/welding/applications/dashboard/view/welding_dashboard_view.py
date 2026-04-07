from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from src.applications.base.i_application_view import IApplicationView
from pl_gui.dashboard.DashboardWidget import DashboardWidget


class WeldingDashboardView(IApplicationView):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    action_requested = pyqtSignal(str)

    def __init__(self, config, action_buttons: list, cards: list, parent=None):
        self._config = config
        self._action_buttons = action_buttons
        self._cards_input = cards
        super().__init__("WeldingDashboard", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._dashboard = DashboardWidget(
            config=self._config,
            action_buttons=self._action_buttons,
            cards=self._cards_input,
        )
        layout.addWidget(self._dashboard)

        self._state_label = QLabel("State: idle")
        self._mode_label = QLabel("Mode: Welding Mode")
        self._job_label = QLabel("Job: No active job")

        self._notes = QTextEdit()
        self._notes.setReadOnly(True)
        self._notes.setPlaceholderText("Dashboard notes")

        self._status_widget = QWidget()
        status_layout = QVBoxLayout(self._status_widget)
        status_layout.setContentsMargins(8, 8, 8, 8)
        status_layout.setSpacing(8)
        status_layout.addWidget(self._state_label)
        status_layout.addWidget(self._mode_label)
        status_layout.addWidget(self._job_label)
        status_layout.addWidget(self._notes, 1)
        self._inject_aux_widget(self._status_widget)

        self._dashboard.start_requested.connect(self.start_requested)
        self._dashboard.stop_requested.connect(self.stop_requested)
        self._dashboard.pause_requested.connect(self.pause_requested)
        self._dashboard.action_requested.connect(self._on_inner_action)

    def _inject_aux_widget(self, widget) -> None:
        try:
            main_layout = self._dashboard.layout_manager.main_layout
            top_section = main_layout.itemAt(0).layout()
            preview_container = top_section.itemAt(0).widget()
            aux_grid = preview_container.layout().itemAt(1).widget()
            aux_layout = aux_grid.layout()
            rows = self._config.preview_aux_rows
            cols = self._config.preview_aux_cols
            aux_layout.addWidget(widget, 0, 0, rows, cols)
        except Exception:
            widget.setParent(self._dashboard)

    def _on_inner_action(self, action_id: str) -> None:
        if action_id == "reset_errors":
            self.reset_requested.emit()
            return
        self.action_requested.emit(action_id)

    def set_trajectory_image(self, image) -> None:
        self._dashboard.set_trajectory_image(image)

    def set_state(self, state: str) -> None:
        self._state_label.setText(f"State: {state}")

    def set_mode(self, mode: str) -> None:
        self._mode_label.setText(f"Mode: {mode}")

    def set_active_job(self, label: str) -> None:
        self._job_label.setText(f"Job: {label}")

    def set_notes(self, lines: list[str]) -> None:
        self._notes.setPlainText("\n".join(lines))

    def set_start_enabled(self, enabled: bool) -> None:
        self._dashboard.set_start_enabled(enabled)

    def set_stop_enabled(self, enabled: bool) -> None:
        self._dashboard.set_stop_enabled(enabled)

    def set_pause_enabled(self, enabled: bool) -> None:
        self._dashboard.set_pause_enabled(enabled)

    def set_pause_label(self, text: str) -> None:
        self._dashboard.set_pause_text(text)

    def apply_dashboard_state(self, state) -> None:
        self.set_state(state.process_state)
        self.set_mode(state.mode_label)
        self.set_active_job(state.active_job_label)
        self.set_notes(state.status_lines)
        self.set_start_enabled(state.can_start)
        self.set_stop_enabled(state.can_stop)
        self.set_pause_enabled(state.can_pause)
        self.set_pause_label(state.pause_label)

    def clean_up(self) -> None:
        pass


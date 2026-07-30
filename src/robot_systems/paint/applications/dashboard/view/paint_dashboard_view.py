from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
)

from src.applications.base.i_application_view import IApplicationView
from pl_gui.dashboard.DashboardWidget import DashboardWidget
from pl_gui.settings.settings_view.styles import BG_COLOR


class PaintDashboardView(IApplicationView):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    action_requested = pyqtSignal(str)

    def __init__(self, config, action_buttons: list, cards: list, parent=None):
        self._config = config
        self._action_buttons = action_buttons
        self._cards_input = cards
        super().__init__("PaintDashboard", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._dashboard = DashboardWidget(
            config=self._config,
            action_buttons=self._action_buttons,
            cards=self._cards_input,
        )
        layout.addWidget(self._dashboard)
        self._dashboard.setStyleSheet(f"background-color: {BG_COLOR};")
        self._align_preview_and_card_columns()
        self._move_reset_below_cards()
        self._expand_process_controls()

        self._dashboard.start_requested.connect(self.start_requested)
        self._dashboard.stop_requested.connect(self.stop_requested)
        self._dashboard.pause_requested.connect(self.pause_requested)
        self._dashboard.action_requested.connect(self._on_inner_action)

    def _align_preview_and_card_columns(self) -> None:
        try:
            main_layout = self._dashboard.layout_manager.main_layout
            top_section = main_layout.itemAt(0).layout()
            preview_container = top_section.itemAt(0).widget()
            preview_container.setStyleSheet(f"background-color: {BG_COLOR};")
            aux_grid = preview_container.layout().itemAt(1).widget()
            aux_grid.setStyleSheet(f"background-color: {BG_COLOR};")
            aux_grid.hide()
            side_panel = top_section.itemAt(1).widget()
            if side_panel is not None:
                side_panel.setStyleSheet(f"background-color: {BG_COLOR};")
                side_panel.setFixedHeight(self._config.trajectory_height + 8)
                top_section.setAlignment(side_panel, Qt.AlignmentFlag.AlignTop)
        except Exception:
            pass

    def _move_reset_below_cards(self) -> None:
        try:
            reset_button = self._dashboard._action_buttons.get("reset_errors")
            if reset_button is None:
                return
            main_layout = self._dashboard.layout_manager.main_layout
            top_section = main_layout.itemAt(0).layout()
            side_panel = top_section.itemAt(1).widget()
            side_layout = side_panel.layout()
            side_layout.addWidget(reset_button, 3, 0)
        except Exception:
            pass

    def _expand_process_controls(self) -> None:
        try:
            main_layout = self._dashboard.layout_manager.main_layout
            bottom_container = main_layout.itemAt(1).widget()
            bottom_layout = bottom_container.layout()
            action_area = bottom_layout.itemAt(0).widget()
            controls = bottom_layout.itemAt(1).widget()
            action_area.hide()
            bottom_layout.setStretchFactor(action_area, 0)
            bottom_layout.setStretchFactor(controls, 1)
        except Exception:
            pass

    def _on_inner_action(self, action_id: str) -> None:
        if action_id == "reset_errors":
            self.reset_requested.emit()
            return
        self.action_requested.emit(action_id)

    def set_trajectory_image(self, image) -> None:
        self._dashboard.set_trajectory_image(image)

    def set_state(self, state: str) -> None:
        _ = state

    def set_mode(self, mode: str) -> None:
        _ = mode

    def set_active_job(self, label: str) -> None:
        _ = label

    def set_notes(self, lines: list[str]) -> None:
        _ = lines

    def set_start_enabled(self, enabled: bool) -> None:
        self._dashboard.set_start_enabled(enabled)

    def set_stop_enabled(self, enabled: bool) -> None:
        self._dashboard.set_stop_enabled(enabled)

    def set_pause_enabled(self, enabled: bool) -> None:
        self._dashboard.set_pause_enabled(enabled)

    def set_pause_label(self, text: str) -> None:
        self._dashboard.set_pause_text(text)

    def set_action_enabled(self, action_id: str, enabled: bool) -> None:
        self._dashboard.set_action_button_enabled(action_id, enabled)

    def show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def show_debug_plot(self, title: str, image_path: str, message: str = "") -> None:
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.show_warning(title, f"Could not load plot image:\n{image_path}")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(1200, 800)

        layout = QVBoxLayout(dialog)
        if message:
            message_label = QLabel(message)
            message_label.setWordWrap(True)
            layout.addWidget(message_label)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setPixmap(pixmap)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(image_label)
        layout.addWidget(scroll, 1)

        dialog.exec()

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

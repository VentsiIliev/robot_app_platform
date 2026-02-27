from __future__ import annotations
from PyQt6.QtCore import pyqtSignal, QEvent
from PyQt6.QtWidgets import QVBoxLayout
from pl_gui.dashboard.DashboardWidget import DashboardWidget
from src.applications.base.i_application_view import IApplicationView
from src.robot_systems.glue.dashboard.ui.system_status_widget import SystemStatusWidget


class GlueDashboardView(IApplicationView):
    """View — pure Qt widget. No broker, no services, no business logic."""

    LOGOUT_REQUEST   = pyqtSignal()
    start_requested  = pyqtSignal()
    pause_requested  = pyqtSignal()
    stop_requested   = pyqtSignal()
    action_requested = pyqtSignal(str)
    language_changed = pyqtSignal()

    def __init__(self, config, action_buttons: list, cards: list, parent=None):
        self._config         = config
        self._action_buttons = action_buttons
        self._cards_input    = cards
        super().__init__("Dashboard", parent)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._dashboard = DashboardWidget(
            config=self._config,
            action_buttons=self._action_buttons,
            cards=self._cards_input,
        )
        layout.addWidget(self._dashboard)
        self._dashboard.start_requested.connect(self._on_inner_start)
        self._dashboard.stop_requested.connect(self._on_inner_stop)
        self._dashboard.pause_requested.connect(self._on_inner_pause)
        self._dashboard.action_requested.connect(self._on_inner_action)

        self._system_status = SystemStatusWidget()
        self._inject_aux_widget(self._system_status)

    def _inject_aux_widget(self, widget) -> None:
        """
        Navigate the DashboardWidget layout tree to find the aux grid container
        and add our widget spanning all rows and columns.

        Layout path (read-only — pl_gui internals):
          DashboardWidget.layout_manager.main_layout [QVBoxLayout]
            itemAt(0).layout()  → top_section [QHBoxLayout]
              itemAt(0).widget() → preview_container [QWidget]
                .layout().itemAt(1).widget() → aux_grid_container [QWidget / QGridLayout]
        """
        try:
            main_layout      = self._dashboard.layout_manager.main_layout
            top_section      = main_layout.itemAt(0).layout()
            preview_container = top_section.itemAt(0).widget()
            aux_grid         = preview_container.layout().itemAt(1).widget()
            aux_layout       = aux_grid.layout()
            rows = self._config.preview_aux_rows
            cols = self._config.preview_aux_cols
            aux_layout.addWidget(widget, 0, 0, rows, cols)
        except Exception as exc:
            import logging
            logging.getLogger(self.__class__.__name__).warning(
                "Could not inject aux widget — layout structure may have changed: %s", exc
            )

    # ── Named forwarders ─────────────────────────────────────────────

    def _on_inner_start(self)          -> None: self.start_requested.emit()
    def _on_inner_stop(self)           -> None: self.stop_requested.emit()
    def _on_inner_pause(self)          -> None: self.pause_requested.emit()
    def _on_inner_action(self, action) -> None: self.action_requested.emit(action)

    # ── System status setters ─────────────────────────────────────────

    def set_process_state(self, state: str)          -> None: self._system_status.set_process_state(state)
    def set_active_process(self, process_id: str)    -> None: self._system_status.set_active_process(process_id)
    def set_system_state(self, state: str)           -> None: self._system_status.set_system_state(state)

    # ── Dashboard setters ─────────────────────────────────────────────

    def set_cell_weight(self, card_id: int, grams: float) -> None:       self._dashboard.set_cell_weight(card_id, grams)
    def set_cell_state(self, card_id: int, state: str) -> None:          self._dashboard.set_cell_state(card_id, state)
    def set_cell_glue_type(self, card_id: int, glue_type: str) -> None:  self._dashboard.set_cell_glue_type(card_id, glue_type)
    def set_trajectory_image(self, image) -> None:                       self._dashboard.set_trajectory_image(image)
    def update_trajectory_point(self, point) -> None:                    self._dashboard.update_trajectory_point(point)
    def break_trajectory(self, _=None) -> None:                          self._dashboard.break_trajectory()
    def enable_trajectory_drawing(self, _=None) -> None:                 self._dashboard.enable_trajectory_drawing()
    def disable_trajectory_drawing(self, _=None) -> None:                self._dashboard.disable_trajectory_drawing()
    def set_start_enabled(self, enabled: bool) -> None:                  self._dashboard.set_start_enabled(enabled)
    def set_stop_enabled(self, enabled: bool) -> None:                   self._dashboard.set_stop_enabled(enabled)
    def set_pause_enabled(self, enabled: bool) -> None:                  self._dashboard.set_pause_enabled(enabled)
    def set_pause_text(self, text: str) -> None:                         self._dashboard.set_pause_text(text)
    def set_action_button_text(self, action_id: str, text: str) -> None: self._dashboard.set_action_button_text(action_id, text)
    def set_action_button_enabled(self, action_id: str, enabled: bool):  self._dashboard.set_action_button_enabled(action_id, enabled)
    def get_card(self, card_id: int):                                     return self._dashboard._cards.get(card_id)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.language_changed.emit()
        super().changeEvent(event)

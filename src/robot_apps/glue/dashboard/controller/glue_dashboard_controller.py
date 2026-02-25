from __future__ import annotations
import logging
from typing import Callable, List, Tuple

from PyQt6.QtCore import QCoreApplication

from src.engine.core.message_broker import MessageBroker
from src.shared_contracts.events.robot_events import RobotTopics
from src.robot_apps.glue.dashboard.config import (
    ACTION_BUTTONS, BUTTON_STATE_MAP, GLUE_CELLS,
    GlueCellTopics, SystemTopics, ApplicationState, MODE_TOGGLE_LABELS,
)
from src.robot_apps.glue.dashboard.model.glue_dashboard_model import GlueDashboardModel
from src.robot_apps.glue.dashboard.view.glue_dashboard_view import GlueDashboardView


class GlueDashboardController:
    """Controller — broker subscriptions + view signal handling. Zero Qt widgets owned."""

    def __init__(self, model: GlueDashboardModel, view: GlueDashboardView, broker: MessageBroker):
        self._model  = model
        self._view   = view
        self._broker = broker
        self._subs: List[Tuple[str, Callable]] = []
        self._mode_index     = 0
        self._current_state  = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def start(self) -> None:
        self._subscribe()
        self._connect_signals()
        self._initialize_view()
        self._view.destroyed.connect(self.stop)

    def stop(self) -> None:
        for topic, cb in reversed(self._subs):
            try: self._broker.unsubscribe(topic, cb)
            except Exception: pass
        self._subs.clear()
        self._disconnect_signals()

    # ------------------------------------------------------------------
    # Broker → View
    # ------------------------------------------------------------------

    def _subscribe(self) -> None:
        for cfg in GLUE_CELLS:
            i = cfg.card_id
            self._sub(GlueCellTopics.weight(i),    lambda g, i=i: self._view.set_cell_weight(i, g))
            self._sub(GlueCellTopics.state(i),     self._make_state_handler(i))
            self._sub(GlueCellTopics.glue_type(i), lambda t, i=i: self._view.set_cell_glue_type(i, t))
        self._sub(RobotTopics.STATE,              self._on_robot_state)
        self._sub(SystemTopics.APPLICATION_STATE, self._on_app_state)

    def _make_state_handler(self, cell_id: int) -> Callable:
        def handler(msg):
            state = msg.get("current_state", "unknown") if isinstance(msg, dict) else str(msg)
            self._view.set_cell_state(cell_id, state)
        return handler

    def _on_robot_state(self, snapshot) -> None:
        state = getattr(snapshot, "state", None)
        if state:
            self._on_app_state(state)

    def _on_app_state(self, data) -> None:
        state = data.get("state", data) if isinstance(data, dict) else str(data)
        self._current_state = state
        cfg = BUTTON_STATE_MAP.get(state)
        if cfg:
            self._view.set_start_enabled(cfg["start"])
            self._view.set_stop_enabled(cfg["stop"])
            self._view.set_pause_enabled(cfg["pause"])
            self._view.set_pause_text(self._t(cfg["pause_text"]))

    # ------------------------------------------------------------------
    # View signals → Model / Broker
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._view.start_requested.connect(self._model.start)
        self._view.stop_requested.connect(self._model.stop)
        self._view.pause_requested.connect(self._on_pause)
        self._view.action_requested.connect(self._on_action)
        self._view.language_changed.connect(self._retranslate)
        for cfg in GLUE_CELLS:
            card = self._view.get_card(cfg.card_id)
            if card and hasattr(card, "change_glue_requested"):
                card.change_glue_requested.connect(self._on_glue_change)

    def _disconnect_signals(self) -> None:
        try:
            self._view.start_requested.disconnect(self._model.start)
            self._view.stop_requested.disconnect(self._model.stop)
            self._view.pause_requested.disconnect(self._on_pause)
            self._view.action_requested.disconnect(self._on_action)
            self._view.language_changed.disconnect(self._retranslate)
        except RuntimeError:
            pass

    def _on_pause(self) -> None:
        self._broker.publish(SystemTopics.APPLICATION_STATE, ApplicationState.PAUSED)

    def _on_action(self, action_id: str) -> None:
        if action_id == "mode_toggle":
            self._mode_index = 1 - self._mode_index
            label = MODE_TOGGLE_LABELS[self._mode_index]
            self._view.set_action_button_text("mode_toggle", self._t(label))
            self._broker.publish(SystemTopics.SYSTEM_MODE_CHANGE, label)
        elif action_id == "clean":
            self._broker.publish(SystemTopics.COMMAND_CLEAN, {})
        elif action_id == "reset_errors":
            self._broker.publish(SystemTopics.COMMAND_RESET, {})

    def _on_glue_change(self, cell_id: int) -> None:
        from src.robot_apps.glue.dashboard.ui.glue_change_guide_wizard import create_glue_change_wizard
        wizard = create_glue_change_wizard(glue_type_names=self._model.get_all_glue_types())
        wizard.setWindowTitle(f"Change Glue for Cell {cell_id}")
        if wizard.exec() == 1:
            page = wizard.page(6)
            selected = page.get_selected_option() if hasattr(page, "get_selected_option") else None
            if selected:
                self._view.set_cell_glue_type(cell_id, selected)

    def _initialize_view(self) -> None:
        for cfg in GLUE_CELLS:
            state = self._model.get_initial_cell_state(cfg.card_id)
            glue_type = self._model.get_cell_glue_type(cfg.card_id)
            if state:
                self._view.set_cell_state(cfg.card_id, state.get("current_state", "unknown"))
            if glue_type:
                self._view.set_cell_glue_type(cfg.card_id, glue_type)

    def _retranslate(self) -> None:
        for btn in ACTION_BUTTONS:
            self._view.set_action_button_text(btn.action_id, self._t(btn.label))
        self._view.set_action_button_text("mode_toggle", self._t(MODE_TOGGLE_LABELS[self._mode_index]))
        if self._current_state:
            cfg = BUTTON_STATE_MAP.get(self._current_state)
            if cfg:
                self._view.set_pause_text(self._t(cfg["pause_text"]))

    def _sub(self, topic: str, cb: Callable) -> None:
        self._broker.subscribe(topic, cb)
        self._subs.append((topic, cb))

    @staticmethod
    def _t(text: str) -> str:
        return QCoreApplication.translate("GlueDashboard", text)
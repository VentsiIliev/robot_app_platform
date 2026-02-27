from __future__ import annotations
import logging
from typing import Callable, List, Tuple

from PyQt6.QtCore import QCoreApplication, QObject, pyqtSignal

from src.engine.core.i_messaging_service import IMessagingService
from src.plugins.base.i_plugin_controller import IPluginController
from src.shared_contracts.events.process_events import ProcessState, ProcessTopics
from src.shared_contracts.events.robot_events import RobotTopics
from src.shared_contracts.events.weight_events import WeightTopics
from src.robot_apps.glue.dashboard.config import (
    ACTION_BUTTONS, BUTTON_STATE_MAP, GLUE_CELLS,
    GlueCellTopics, MODE_TOGGLE_LABELS,
)
from src.robot_apps.glue.dashboard.model.glue_dashboard_model import GlueDashboardModel
from src.robot_apps.glue.dashboard.view.glue_dashboard_view import GlueDashboardView

_PROCESS_ID = "glue"


class _DashboardBridge(QObject):
    weight_reading = pyqtSignal(int, float)
    cell_state     = pyqtSignal(int, str)
    glue_type      = pyqtSignal(int, str)
    robot_state    = pyqtSignal(str)
    process_state  = pyqtSignal(str)   # ProcessState.value from BaseProcess


class GlueDashboardController(IPluginController):

    def __init__(self, model: GlueDashboardModel, view: GlueDashboardView, broker: IMessagingService):
        self._model         = model
        self._view          = view
        self._broker        = broker
        self._subs:         List[Tuple[str, Callable]] = []
        self._mode_index    = 0
        self._current_state = ProcessState.IDLE.value
        self._active        = False
        self._logger        = logging.getLogger(self.__class__.__name__)
        self._bridge        = _DashboardBridge()

    def load(self) -> None:
        self._active = True
        self._wire_bridge()
        self._subscribe()
        self._connect_signals()
        self._initialize_view()
        self._view.destroyed.connect(self.stop)

    def stop(self) -> None:
        self._active = False
        for topic, cb in reversed(self._subs):
            try: self._broker.unsubscribe(topic, cb)
            except Exception: pass
        self._subs.clear()
        self._disconnect_signals()

    # ── Guard ─────────────────────────────────────────────────────────

    def _view_ok(self) -> bool:
        if not self._active:
            return False
        try:
            _ = self._view.isVisible()
            return True
        except RuntimeError:
            return False

    # ── Bridge wiring ─────────────────────────────────────────────────

    def _wire_bridge(self) -> None:
        self._bridge.weight_reading.connect(self._on_weight)
        self._bridge.cell_state.connect(self._on_cell_state)
        self._bridge.glue_type.connect(self._on_glue_type)
        self._bridge.robot_state.connect(self._on_robot_state_str)
        self._bridge.process_state.connect(self._on_process_state_str)

    # ── Broker → Bridge ───────────────────────────────────────────────

    def _subscribe(self) -> None:
        for cfg in GLUE_CELLS:
            card_id = cfg.card_id
            cell_id = card_id - 1
            self._sub(WeightTopics.reading(cell_id),
                      lambda r, cid=card_id: self._bridge.weight_reading.emit(cid, r.value))
            self._sub(WeightTopics.state(cell_id),
                      lambda e, cid=card_id: self._bridge.cell_state.emit(cid, e.state.value))
            self._sub(GlueCellTopics.glue_type(card_id),
                      lambda t, cid=card_id: self._bridge.glue_type.emit(cid, t))

        self._sub(RobotTopics.STATE,
                  lambda s: self._bridge.robot_state.emit(getattr(s, "state", "") or ""))
        self._sub(ProcessTopics.state(_PROCESS_ID),
                  lambda e: self._bridge.process_state.emit(e.state.value))

    # ── Bridge slots (main thread) ─────────────────────────────────────

    def _on_weight(self, card_id: int, grams: float) -> None:
        if self._view_ok():
            self._view.set_cell_weight(card_id, grams)

    def _on_cell_state(self, card_id: int, state: str) -> None:
        if self._view_ok():
            self._view.set_cell_state(card_id, state)

    def _on_glue_type(self, card_id: int, glue_type: str) -> None:
        if self._view_ok():
            self._view.set_cell_glue_type(card_id, glue_type)

    def _on_robot_state_str(self, state: str) -> None:
        # only update buttons from robot state when no process state has been received
        if self._view_ok() and self._current_state == ProcessState.IDLE.value and state:
            self._apply_button_state(state)

    def _on_process_state_str(self, state: str) -> None:
        if self._view_ok():
            self._apply_button_state(state)

    # ── View signals → Model ──────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._view.start_requested.connect(self._on_start)
        self._view.stop_requested.connect(self._on_stop)
        self._view.pause_requested.connect(self._on_pause)
        self._view.action_requested.connect(self._on_action)
        self._view.language_changed.connect(self._retranslate)
        for cfg in GLUE_CELLS:
            card = self._view.get_card(cfg.card_id)
            if card and hasattr(card, "change_glue_requested"):
                card.change_glue_requested.connect(self._on_glue_change)

    def _disconnect_signals(self) -> None:
        if not self._view_ok():
            return
        try:
            self._view.start_requested.disconnect(self._on_start)
            self._view.stop_requested.disconnect(self._on_stop)
            self._view.pause_requested.disconnect(self._on_pause)
            self._view.action_requested.disconnect(self._on_action)
            self._view.language_changed.disconnect(self._retranslate)
        except RuntimeError:
            pass

    def _on_start(self) -> None:
        if not self._active: return
        self._model.start()   # BaseProcess publishes → bridge → _apply_button_state

    def _on_stop(self) -> None:
        if not self._active: return
        self._model.stop()

    def _on_pause(self) -> None:
        if not self._active: return
        if self._current_state == ProcessState.PAUSED.value:
            self._model.start()   # BaseProcess.start() detects PAUSED → calls _on_resume
        else:
            self._model.pause()

    def _on_action(self, action_id: str) -> None:
        if not self._active: return
        if action_id == "mode_toggle":
            self._mode_index = 1 - self._mode_index
            label = MODE_TOGGLE_LABELS[self._mode_index]
            self._view.set_action_button_text("mode_toggle", self._t(label))
            self._model.set_mode(label)
        elif action_id == "clean":
            self._model.clean()
        elif action_id == "reset_errors":
            self._model.reset_errors()

    def _on_glue_change(self, card_id: int) -> None:
        if not self._active: return
        from PyQt6.QtWidgets import QDialog
        from src.robot_apps.glue.dashboard.ui.glue_change_guide_wizard import create_glue_change_wizard
        cell_id    = int(card_id) - 1
        glue_types = self._model.get_all_glue_types()
        wizard     = create_glue_change_wizard(glue_type_names=glue_types)
        wizard.setWindowTitle(f"Change Glue for Cell {card_id}")
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        page = wizard.page(6)
        if page is None:
            return
        selected = page.get_selected_option() if hasattr(page, "get_selected_option") else None
        if not selected:
            return
        self._model.change_glue(cell_id, selected)
        self._view.set_cell_glue_type(card_id, selected)
        self._broker.publish(GlueCellTopics.glue_type(card_id), selected)

    # ── State machine ─────────────────────────────────────────────────

    def _apply_button_state(self, state: str) -> None:
        if not self._view_ok(): return
        self._current_state = state
        cfg = BUTTON_STATE_MAP.get(state)
        if cfg:
            self._view.set_start_enabled(cfg["start"])
            self._view.set_stop_enabled(cfg["stop"])
            self._view.set_pause_enabled(cfg["pause"])
            self._view.set_pause_text(self._t(cfg["pause_text"]))
            self._view.set_action_button_enabled("mode_toggle", cfg["mode_toggle"])
            self._view.set_action_button_enabled("clean", cfg["clean"])
            self._view.set_action_button_enabled("reset_errors", cfg["reset_errors"])

    # ── Initialize ────────────────────────────────────────────────────

    def _initialize_view(self) -> None:
        self._apply_button_state(ProcessState.IDLE.value)
        for cfg in GLUE_CELLS:
            card_id   = cfg.card_id
            cell_id   = card_id - 1
            glue_type = self._model.get_cell_glue_type(cell_id)
            if glue_type:
                self._view.set_cell_glue_type(card_id, glue_type)
            state = self._model.get_cell_connection_state(cell_id)
            self._view.set_cell_state(card_id, state)

    # ── Localization ──────────────────────────────────────────────────

    def _retranslate(self) -> None:
        if not self._view_ok(): return
        for btn in ACTION_BUTTONS:
            self._view.set_action_button_text(btn.action_id, self._t(btn.label))
        self._view.set_action_button_text("mode_toggle", self._t(MODE_TOGGLE_LABELS[self._mode_index]))
        cfg = BUTTON_STATE_MAP.get(self._current_state)
        if cfg:
            self._view.set_pause_text(self._t(cfg["pause_text"]))

    def _sub(self, topic: str, cb: Callable) -> None:
        self._broker.subscribe(topic, cb)
        self._subs.append((topic, cb))

    @staticmethod
    def _t(text: str) -> str:
        return QCoreApplication.translate("GlueDashboard", text)

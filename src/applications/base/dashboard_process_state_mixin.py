from __future__ import annotations

from PyQt6.QtCore import pyqtSignal

from src.applications.base.broker_subscription_mixin import SignalBridge
from src.shared_contracts.events.process_events import ProcessTopics


class _DashboardProcessBridge(SignalBridge):
    state_ready = pyqtSignal(object)


class DashboardProcessStateMixin:
    """
    Shared dashboard process-state wiring.

    Assumptions:
    - controller has `_model` with `_service`
    - dashboard service exposes `get_process_id()`
    - controller has either `_sub(topic, callback)` or `_subscribe(topic, callback)`
    - model exposes `load()`
    - view exposes `apply_dashboard_state(state)`
    """

    def _init_dashboard_process_state(self) -> None:
        self._dashboard_process_bridge = _DashboardProcessBridge()
        apply_state = getattr(self._view, "apply_dashboard_state", None)
        if not callable(apply_state):
            raise RuntimeError(
                f"{type(self._view).__name__} must implement apply_dashboard_state() to use DashboardProcessStateMixin"
            )
        self._dashboard_process_bridge.state_ready.connect(apply_state)

    def _subscribe_dashboard_process_state(self) -> None:
        subscribe = getattr(self, "_sub", None) or getattr(self, "_subscribe", None)
        if not callable(subscribe):
            raise RuntimeError(
                f"{self.__class__.__name__} must provide _sub() or _subscribe() to use DashboardProcessStateMixin"
            )
        subscribe(ProcessTopics.ACTIVE, self._on_dashboard_process_state_raw)

    def _on_dashboard_process_state_raw(self, event: object) -> None:
        service = getattr(getattr(self, "_model", None), "_service", None)
        if service is None:
            return
        process_id_getter = getattr(service, "get_process_id", None)
        if not callable(process_id_getter):
            raise RuntimeError(
                f"{type(service).__name__} must implement get_process_id() to use DashboardProcessStateMixin"
            )
        if getattr(event, "process_id", None) != process_id_getter():
            return
        state = self._model.load()
        self._dashboard_process_bridge.state_ready.emit(state)

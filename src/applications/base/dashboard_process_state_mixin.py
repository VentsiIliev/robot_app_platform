from __future__ import annotations

from PyQt6.QtCore import pyqtSignal

from src.applications.base.broker_subscription_mixin import SignalBridge
from src.shared_contracts.events.process_events import ProcessTopics


class _DashboardProcessBridge(SignalBridge):
    state_ready = pyqtSignal(object)
    warning_ready = pyqtSignal(str, str)


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
        self._last_dashboard_error_message = ""
        show_warning = getattr(self._view, "show_warning", None)
        if callable(show_warning):
            self._dashboard_process_bridge.warning_ready.connect(show_warning)

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
        if self._process_id_value(getattr(event, "process_id", None)) != self._process_id_value(process_id_getter()):
            return
        state = self._model.load()
        self._dashboard_process_bridge.state_ready.emit(state)
        message = str(getattr(event, "message", "") or "").strip()
        event_state = str(getattr(getattr(event, "state", None), "value", getattr(event, "state", "")) or "")
        warning = self._dashboard_warning_for_event(event_state, message)
        if warning is not None:
            title, warning_message = warning
            warning_key = f"{event_state}:{title}:{warning_message}"
            if warning_key != self._last_dashboard_error_message:
                self._last_dashboard_error_message = warning_key
                self._dashboard_process_bridge.warning_ready.emit(title, warning_message)
        elif event_state not in {"error", "stopped"}:
            self._last_dashboard_error_message = ""

    @staticmethod
    def _process_id_value(process_id: object) -> str:
        return str(getattr(process_id, "value", process_id))

    @classmethod
    def _dashboard_warning_for_event(cls, event_state: str, message: str) -> tuple[str, str] | None:
        if not message:
            return None
        if cls._is_no_workpiece_message(message):
            return (
                "No Workpiece Found",
                "No workpiece was found in the camera view. Place a workpiece in the active area and start again.",
            )
        if event_state == "error":
            return "Process Blocked", message
        return None

    @staticmethod
    def _is_no_workpiece_message(message: str) -> bool:
        lowered = str(message or "").strip().lower()
        return (
            "no workpiece" in lowered
            or "no usable contour detected" in lowered
            or "magazine empty" in lowered
        )

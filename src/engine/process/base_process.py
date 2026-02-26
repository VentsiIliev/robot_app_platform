from __future__ import annotations
import logging
import threading
from typing import Callable, Dict, FrozenSet

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.i_process import IProcess
from src.engine.process.process_state import ProcessState, ProcessStateEvent, ProcessTopics

_TRANSITIONS: Dict[ProcessState, FrozenSet[ProcessState]] = {
    ProcessState.IDLE:    frozenset({ProcessState.RUNNING}),
    ProcessState.RUNNING: frozenset({ProcessState.PAUSED, ProcessState.STOPPED, ProcessState.ERROR}),
    ProcessState.PAUSED:  frozenset({ProcessState.RUNNING, ProcessState.STOPPED, ProcessState.ERROR}),
    ProcessState.STOPPED: frozenset({ProcessState.RUNNING, ProcessState.IDLE}),
    ProcessState.ERROR:   frozenset({ProcessState.IDLE}),
}


class BaseProcess(IProcess):
    """
    Thread-safe state machine + broker publishing.

    Subclasses override the _on_* hooks to inject app-specific behaviour.
    All hooks are called while the lock is held — keep them non-blocking.
    If a hook raises, the state is forced to ERROR and the exception is logged.
    """

    def __init__(self, process_id: str, messaging: IMessagingService):
        self._process_id = process_id
        self._messaging  = messaging
        self._state      = ProcessState.IDLE
        self._lock       = threading.Lock()
        self._logger     = logging.getLogger(f"Process[{process_id}]")

    @property
    def process_id(self) -> str:
        return self._process_id

    @property
    def state(self) -> ProcessState:
        return self._state

    # ── IProcess ──────────────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._state == ProcessState.PAUSED:
                self._transition(ProcessState.RUNNING, self._on_resume)
            else:
                self._transition(ProcessState.RUNNING, self._on_start)

    def stop(self) -> None:
        with self._lock:
            self._transition(ProcessState.STOPPED, self._on_stop)

    def pause(self) -> None:
        with self._lock:
            self._transition(ProcessState.PAUSED, self._on_pause)

    def resume(self) -> None:
        with self._lock:
            self._transition(ProcessState.RUNNING, self._on_resume)

    def reset_errors(self) -> None:
        with self._lock:
            self._transition(ProcessState.IDLE, self._on_reset_errors)

    def set_error(self, message: str = "") -> None:
        """Force ERROR state from a subclass (e.g. hardware fault detected)."""
        with self._lock:
            previous    = self._state
            self._state = ProcessState.ERROR
            self._publish(ProcessState.ERROR, previous, message)

    # ── Template methods ──────────────────────────────────────────────

    def _on_start(self)        -> None: ...
    def _on_stop(self)         -> None: ...
    def _on_pause(self)        -> None: ...
    def _on_resume(self)       -> None: ...
    def _on_reset_errors(self) -> None: ...

    # ── Internal ──────────────────────────────────────────────────────

    def _transition(self, target: ProcessState, action: Callable, message: str = "") -> None:
        allowed = _TRANSITIONS.get(self._state, frozenset())
        if target not in allowed:
            self._logger.warning(
                "Invalid transition %s → %s (allowed: %s)",
                self._state.value, target.value, {s.value for s in allowed},
            )
            return
        previous    = self._state
        self._state = target
        try:
            action()
        except Exception as exc:
            self._logger.exception("Hook error during %s → %s", previous.value, target.value)
            self._state = ProcessState.ERROR
            self._publish(ProcessState.ERROR, previous, str(exc))
            return
        self._publish(target, previous, message)

    def _publish(self, state: ProcessState, previous: ProcessState, message: str = "") -> None:
        event = ProcessStateEvent(
            process_id = self._process_id,
            state      = state,
            previous   = previous,
            message    = message,
        )
        self._messaging.publish(ProcessTopics.state(self._process_id), event)
        self._logger.info("%s → %s", previous.value, state.value)
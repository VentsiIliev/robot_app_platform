from __future__ import annotations
import logging
import threading
from typing import Callable, Dict, FrozenSet, Optional

from src.engine.system.i_system_manager import ISystemManager
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.i_process import IProcess
from src.engine.process.process_requirements import ProcessRequirements
from src.shared_contracts.events.process_events import ProcessState, ProcessTopics, ProcessStateEvent

_TRANSITIONS: Dict[ProcessState, FrozenSet[ProcessState]] = {
    ProcessState.IDLE:    frozenset({ProcessState.RUNNING}),
    ProcessState.RUNNING: frozenset({ProcessState.PAUSED, ProcessState.STOPPED, ProcessState.ERROR}),
    ProcessState.PAUSED:  frozenset({ProcessState.RUNNING, ProcessState.STOPPED, ProcessState.ERROR}),
    ProcessState.STOPPED: frozenset({ProcessState.RUNNING, ProcessState.IDLE}),
    ProcessState.ERROR:   frozenset({ProcessState.IDLE}),
}

_RELEASE_ON: FrozenSet[ProcessState] = frozenset({ProcessState.STOPPED, ProcessState.IDLE})


class BaseProcess(IProcess):
    """
    Thread-safe state machine + broker publishing.

    Optional ISystemManager enforces single-process exclusivity.
    Optional ProcessRequirements + service_checker enforces that all
    required services are available before a RUNNING transition is allowed.
    """

    def __init__(
        self,
        process_id:      str,
        messaging:       IMessagingService,
        system_manager:     Optional[ISystemManager]    = None,
        requirements:    Optional[ProcessRequirements]    = None,
        service_checker: Optional[Callable[[str], bool]]  = None,
    ):
        self._process_id     = process_id
        self._messaging      = messaging
        self._system_manager    = system_manager
        self._requirements   = requirements   or ProcessRequirements.none()
        self._service_checker = service_checker or (lambda _: True)
        self._state          = ProcessState.IDLE
        self._lock           = threading.Lock()
        self._logger         = logging.getLogger(f"Process[{process_id}]")

    @property
    def process_id(self) -> str:
        return self._process_id

    @property
    def state(self) -> ProcessState:
        return self._state

    @property
    def requirements(self) -> ProcessRequirements:
        return self._requirements

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
        if target == ProcessState.RUNNING:
            # 1 — check required services first
            missing = self._requirements.missing_from(self._service_checker)
            if missing:
                self._logger.warning(
                    "Cannot start '%s' — required services unavailable: %s",
                    self._process_id, missing,
                )
                return

            # 2 — acquire system-level lock
            if self._system_manager is not None:
                if not self._system_manager.acquire(self._process_id):
                    return

        allowed = _TRANSITIONS.get(self._state, frozenset())
        if target not in allowed:
            self._logger.warning(
                "Invalid transition %s → %s (allowed: %s)",
                self._state.value, target.value, {s.value for s in allowed},
            )
            if target == ProcessState.RUNNING:
                if self._system_manager:
                    self._system_manager.release(self._process_id)
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

        if target in _RELEASE_ON and self._system_manager:
            self._system_manager.release(self._process_id)

        self._publish(target, previous, message)

    def _publish(self, state: ProcessState, previous: ProcessState, message: str = "") -> None:
        event = ProcessStateEvent(
            process_id=self._process_id,
            state=state,
            previous=previous,
            message=message,
        )
        # ACTIVE first — dashboard receives this state before any chain fires.
        # The specific topic is published second — if a subscriber (e.g., GlueOperationRunner)
        # chains to another process, that process's ACTIVE(RUNNING) will arrive after this
        # ACTIVE event, correctly overriding it in the dashboard.
        self._messaging.publish(ProcessTopics.ACTIVE, event)
        self._messaging.publish(ProcessTopics.state(self._process_id), event)
        self._logger.info("%s → %s", previous.value, state.value)

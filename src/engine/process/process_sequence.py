from __future__ import annotations
import logging
import threading
from typing import List, Optional

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.i_process import IProcess
from src.shared_contracts.events.process_events import ProcessState, ProcessStateEvent, ProcessTopics


class ProcessSequence:
    """
    Executes a list of IProcess instances in order.

    On start():
        - If current process is PAUSED → resume it
        - Otherwise → reset index, start from process[0]

    On natural completion of process[i] (STOPPED state):
        - Auto-advances to process[i+1].start()
        - When the last process stops the sequence is done — no further action

    stop() / pause() always target the currently active process.
    Cancels any pending auto-advance.

    Lives in engine/process — has no knowledge of glue, cleaning, or any
    specific robot application.
    """

    def __init__(
        self,
        processes: List[IProcess],
        messaging: IMessagingService,
    ) -> None:
        if not processes:
            raise ValueError("ProcessSequence requires at least one process")
        self._processes     = list(processes)
        self._messaging     = messaging
        self._current_index = 0
        self._current:      Optional[IProcess] = None
        self._lock          = threading.Lock()
        self._logger        = logging.getLogger(self.__class__.__name__)

    # ── Public API ────────────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._current is not None and self._current.state == ProcessState.PAUSED:
                process = self._current          # resume — do not reset index
            else:
                self._unsubscribe_current()
                self._current_index = 0
                self._current = self._processes[0]
                self._subscribe_current()
                process = self._current
        process.start()

    def stop(self) -> None:
        with self._lock:
            self._unsubscribe_current()
            process = self._current
        if process is not None:
            process.stop()

    def pause(self) -> None:
        with self._lock:
            process = self._current
        if process is not None:
            process.pause()

    def reset_errors(self) -> None:
        with self._lock:
            self._unsubscribe_current()
            process       = self._current
            self._current = None
            self._current_index = 0
        if process is not None:
            process.reset_errors()

    # ── Chain ─────────────────────────────────────────────────────────

    def _subscribe_current(self) -> None:
        if self._current is not None:
            self._messaging.subscribe(
                ProcessTopics.state(self._current.process_id),
                self._on_current_stopped,
            )

    def _unsubscribe_current(self) -> None:
        if self._current is not None:
            try:
                self._messaging.unsubscribe(
                    ProcessTopics.state(self._current.process_id),
                    self._on_current_stopped,
                )
            except Exception:
                pass

    def _on_current_stopped(self, event: ProcessStateEvent) -> None:
        """Bound method — kept alive by self. Called when the active process stops."""
        if event.state != ProcessState.STOPPED:
            return

        with self._lock:
            self._unsubscribe_current()
            next_index = self._current_index + 1

            if next_index >= len(self._processes):
                self._current = None
                self._current_index = 0
                return                             # sequence complete

            self._current_index = next_index
            self._current = self._processes[next_index]
            self._subscribe_current()
            next_process = self._current

        self._logger.info(
            "Sequence advancing [%d/%d] → '%s'",
            next_index + 1, len(self._processes), next_process.process_id,
        )
        next_process.start()
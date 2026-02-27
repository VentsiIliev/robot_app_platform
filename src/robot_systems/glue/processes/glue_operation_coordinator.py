from __future__ import annotations
import logging
import threading
from typing import Dict, Optional

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.process_sequence import ProcessSequence
from src.robot_systems.glue.processes.clean_process import CleanProcess
from src.robot_systems.glue.processes.glue_operation_mode import GlueOperationMode
from src.robot_systems.glue.processes.glue_process import GlueProcess
from src.robot_systems.glue.processes.pick_and_place_process import PickAndPlaceProcess


class GlueOperationCoordinator:
    """
    Maps GlueOperationMode → ProcessSequence and delegates all commands.

    SPRAY_ONLY:    [GlueProcess]
    PICK_AND_SPRAY:[PickAndPlaceProcess → GlueProcess]
    clean():       [CleanProcess]  (standalone, interrupts any active sequence)

    Adding a new mode = add one entry to _sequences. Zero logic changes.
    """

    def __init__(
        self,
        glue_process:           GlueProcess,
        pick_and_place_process: PickAndPlaceProcess,
        clean_process:          CleanProcess,
        messaging:              IMessagingService,
    ) -> None:
        self._sequences: Dict[GlueOperationMode, ProcessSequence] = {
            GlueOperationMode.SPRAY_ONLY:     ProcessSequence([glue_process],                          messaging),
            GlueOperationMode.PICK_AND_SPRAY: ProcessSequence([pick_and_place_process, glue_process],  messaging),
        }
        self._clean_sequence   = ProcessSequence([clean_process], messaging)
        self._mode             = GlueOperationMode.SPRAY_ONLY
        self._active:          Optional[ProcessSequence] = None
        self._lock             = threading.Lock()
        self._logger           = logging.getLogger(self.__class__.__name__)

    # ── Public API ────────────────────────────────────────────────────

    def set_mode(self, mode: GlueOperationMode) -> None:
        with self._lock:
            self._mode = mode
            self._logger.info("Mode → %s", mode.value)

    def start(self) -> None:
        with self._lock:
            self._active = self._sequences[self._mode]
            sequence = self._active
        sequence.start()

    def stop(self) -> None:
        with self._lock:
            sequence = self._active
        if sequence is not None:
            sequence.stop()

    def pause(self) -> None:
        with self._lock:
            sequence = self._active
        if sequence is not None:
            sequence.pause()

    def resume(self) -> None:
        with self._lock:
            sequence = self._active
        if sequence is not None:
            sequence.start()    # ProcessSequence.start() detects PAUSED → resumes

    def clean(self) -> None:
        with self._lock:
            if self._active is not None:
                stopping = self._active
            else:
                stopping = None
            self._active = self._clean_sequence
            sequence = self._active
        if stopping is not None and stopping is not self._clean_sequence:
            stopping.stop()
        sequence.start()

    def reset_errors(self) -> None:
        with self._lock:
            sequence = self._active
        if sequence is not None:
            sequence.reset_errors()

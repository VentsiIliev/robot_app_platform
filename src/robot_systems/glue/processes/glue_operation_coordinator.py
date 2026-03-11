from __future__ import annotations
import logging
import threading
from typing import Dict, Optional

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.process_sequence import ProcessSequence
from src.robot_systems.glue.process_ids import ProcessID
from src.robot_systems.glue.processes.robot_calibration_process import RobotCalibrationProcess
from src.robot_systems.glue.processes.clean_process import CleanProcess
from src.robot_systems.glue.processes.glue_operation_mode import GlueOperationMode
from src.robot_systems.glue.processes.glue_process import GlueProcess
from src.robot_systems.glue.processes.pick_and_place_process import PickAndPlaceProcess
from src.shared_contracts.events.process_events import ProcessBusyEvent, ProcessTopics



from src.engine.process.i_process import IProcess
from src.shared_contracts.events.process_events import ProcessState


class GlueOperationCoordinator:

    def __init__(
        self,
        glue_process:           GlueProcess,
        pick_and_place_process: PickAndPlaceProcess,
        clean_process:          CleanProcess,
        calibration_process:    RobotCalibrationProcess,
        messaging:              IMessagingService,
    ) -> None:
        self._sequences: Dict[GlueOperationMode, ProcessSequence] = {
            GlueOperationMode.SPRAY_ONLY:     ProcessSequence([glue_process],                         messaging),
            GlueOperationMode.PICK_AND_SPRAY: ProcessSequence([pick_and_place_process, glue_process], messaging),
        }
        self._clean_sequence       = ProcessSequence([clean_process], messaging)
        self._calibration_process  = calibration_process
        self._messaging            = messaging
        self._mode                 = GlueOperationMode.SPRAY_ONLY
        self._active_sequence: Optional[ProcessSequence] = None
        self._active_process:  Optional[IProcess]        = None
        self._lock             = threading.Lock()
        self._logger           = logging.getLogger(self.__class__.__name__)

    @property
    def _active(self) -> Optional[ProcessSequence]:
        return self._active_sequence

    @property
    def pick_and_place_process(self) -> PickAndPlaceProcess:
        return self._sequences[GlueOperationMode.PICK_AND_SPRAY]._processes[0]


    def _any_running(self) -> bool:
        if self._active_sequence is not None and self._active_sequence.is_running:
            return True
        if self._active_process is not None and self._active_process.state in (
            ProcessState.RUNNING, ProcessState.PAUSED
        ):
            return True
        return False

    def _reject_if_busy(self, requester: str) -> bool:
        if self._any_running():
            self._messaging.publish(
                ProcessTopics.busy(ProcessID.COORDINATOR),
                ProcessBusyEvent(
                    requested_by=requester,
                    message=f"Cannot start '{requester}' — another process is currently running",
                ),
            )
            self._logger.warning("'%s' rejected — another process is running", requester)
            return True
        return False

    # ── Operation sequences ───────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            self._active_sequence = self._sequences[self._mode]
            sequence = self._active_sequence
        sequence.start()

    def stop(self) -> None:
        with self._lock:
            sequence = self._active_sequence
        if sequence is not None:
            sequence.stop()

    def pause(self) -> None:
        with self._lock:
            sequence = self._active_sequence
        if sequence is not None:
            sequence.pause()

    def resume(self) -> None:
        with self._lock:
            sequence = self._active_sequence
        if sequence is not None:
            sequence.start()

    def reset_errors(self) -> None:
        with self._lock:
            sequence = self._active_sequence
            process  = self._active_process
        if sequence is not None:
            sequence.reset_errors()
        if process is not None:
            process.reset_errors()

    def get_active_state(self) -> str:
        """Return the state of the currently active process, or IDLE if none."""
        with self._lock:
            seq  = self._active_sequence
            proc = self._active_process
        if seq is not None and seq._current is not None:
            return seq._current.state.value
        if proc is not None:
            return proc.state.value
        return ProcessState.IDLE.value

    def set_mode(self, mode: GlueOperationMode) -> None:
        with self._lock:
            self._mode = mode

    # ── Standalone single-process operations ──────────────────────────

    def clean(self) -> None:
        with self._lock:
            current = self._active_sequence
            if current is not None and current is not self._clean_sequence:
                current.stop()
            self._active_sequence = self._clean_sequence
            sequence = self._clean_sequence
        sequence.start()

    def calibrate(self) -> None:
        with self._lock:
            if self._reject_if_busy("calibration"):
                return
            if self._calibration_process.state == ProcessState.ERROR:
                self._logger.info("Auto-resetting calibration from ERROR before start")
                self._calibration_process.reset_errors()
            self._active_process = self._calibration_process
            process = self._calibration_process
        process.start()

    def stop_calibration(self) -> None:
        with self._lock:
            if self._active_process is self._calibration_process:
                self._active_process = None
                process = self._calibration_process
            else:
                process = None
        if process is not None:
            process.stop()


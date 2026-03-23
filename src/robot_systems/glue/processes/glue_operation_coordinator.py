from __future__ import annotations
import logging
import threading
from typing import Dict, Optional

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.process_sequence import ProcessSequence
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.robot_systems.glue.component_ids import ProcessID
from src.robot_systems.glue.component_ids import SettingsID
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
        execution_service=None,
        settings_service:       ISettingsService | None = None,
    ) -> None:
        self._glue_process = glue_process
        self._pick_and_place_process = pick_and_place_process
        self._sequences: Dict[GlueOperationMode, ProcessSequence] = {
            GlueOperationMode.SPRAY_ONLY:     ProcessSequence([glue_process], messaging),
            GlueOperationMode.PICK_AND_SPRAY: ProcessSequence(
                [pick_and_place_process, glue_process],
                messaging,
                before_next_start=self._prepare_glue_after_pick,
            ),
        }
        self._clean_sequence       = ProcessSequence([clean_process], messaging)
        self._calibration_process  = calibration_process
        self._messaging            = messaging
        self._execution_service    = execution_service
        self._settings_service     = settings_service
        self._mode                 = GlueOperationMode.SPRAY_ONLY
        self._active_sequence: Optional[ProcessSequence] = None
        self._active_process:  Optional[IProcess]        = None
        self._lock             = threading.Lock()
        self._logger           = logging.getLogger(self.__class__.__name__)
        self._preparing_glue   = False

    @property
    def _active(self) -> Optional[ProcessSequence]:
        return self._active_sequence

    @property
    def pick_and_place_process(self) -> PickAndPlaceProcess:
        return self._pick_and_place_process

    @property
    def glue_process(self) -> GlueProcess:
        return self._glue_process


    def _any_running(self) -> bool:
        if self._active_sequence is not None and self._active_sequence.is_running:
            return True
        if self._active_process is not None and self._active_process.state in (
            ProcessState.RUNNING, ProcessState.PAUSED
        ):
            return True
        return False

    def _get_configured_spray_on(self) -> bool:
        if self._settings_service is None:
            return True

        settings = self._settings_service.get(SettingsID.GLUE_SETTINGS)
        return bool(getattr(settings, "spray_on", True))

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

    def _is_resuming_active_spray_sequence(self) -> bool:
        with self._lock:
            sequence = self._active_sequence
        return (
            sequence is self._sequences[GlueOperationMode.SPRAY_ONLY]
            and self._glue_process.state == ProcessState.PAUSED
        )

    # ── Operation sequences ───────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            mode = self._mode
            sequence = self._sequences[mode]
            active_sequence = self._active_sequence

        should_prepare = (
            mode == GlueOperationMode.SPRAY_ONLY
            and self._execution_service is not None
            and not self._is_resuming_active_spray_sequence()
        )

        if should_prepare:
            with self._lock:
                self._preparing_glue = True
            try:
                result = self._execution_service.prepare_and_load(
                    spray_on=self._get_configured_spray_on()
                )
            finally:
                with self._lock:
                    self._preparing_glue = False
            if not result.success:
                self._messaging.publish(
                    ProcessTopics.busy(ProcessID.COORDINATOR),
                    ProcessBusyEvent(
                        requested_by=ProcessID.GLUE,
                        message=f"Glue spray-only start failed at {result.stage}: {result.message}",
                    ),
                )
                self._logger.error(
                    "Glue spray-only start failed at %s: %s",
                    result.stage,
                    result.message,
                )
                return

        with self._lock:
            self._active_sequence = sequence
        sequence.start()

    def stop(self) -> None:
        with self._lock:
            sequence = self._active_sequence
            preparing_glue = self._preparing_glue
        if preparing_glue and self._execution_service is not None:
            self._execution_service.cancel_pending()
        if sequence is not None:
            sequence.stop()

    def pause(self) -> None:
        with self._lock:
            sequence = self._active_sequence
            preparing_glue = self._preparing_glue
        if preparing_glue and self._execution_service is not None:
            self._execution_service.cancel_pending()
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

    def get_mode(self) -> GlueOperationMode:
        with self._lock:
            return self._mode

    def _prepare_glue_after_pick(self, current_process: IProcess, next_process: IProcess) -> bool:
        if (
            self._execution_service is None
            or current_process is not self.pick_and_place_process
            or next_process is not self.glue_process
        ):
            return True

        with self._lock:
            self._preparing_glue = True
        try:
            result = self._execution_service.prepare_and_load(
                spray_on=self._get_configured_spray_on()
            )
        finally:
            with self._lock:
                self._preparing_glue = False
        if result.success:
            return True

        message = f"Glue preparation failed at {result.stage}: {result.message}"
        if hasattr(self.glue_process, "set_error"):
            self.glue_process.set_error(message)
        self._logger.error(message)
        return False

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

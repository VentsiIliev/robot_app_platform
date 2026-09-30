from __future__ import annotations

import threading
from typing import Callable, Optional

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.process.base_process import BaseProcess
from src.engine.process.process_requirements import ProcessRequirements
from src.shared_contracts.events.process_events import ProcessState
from src.engine.system.i_system_manager import ISystemManager
from src.robot_systems.paint.component_ids import ProcessID
from src.robot_systems.paint.processes.paint.config import PAINT_PROCESS_CONFIG
from src.robot_systems.paint.processes.paint.incremental_adjustment import (
    AdjustmentStep,
    PaintAdjustmentSession,
)


class PaintProcess(BaseProcess):
    """Run one paint production cycle in the background and report process state changes."""
    def __init__(
        self,
        production_service,
        messaging: IMessagingService,
        robot_service: Optional[IRobotService] = None,
        vacuum_pump: Optional[IVacuumPumpController] = None,
        paint_process_config_service=None,
        system_manager: Optional[ISystemManager] = None,
        requirements: Optional[ProcessRequirements] = None,
        service_checker: Optional[Callable[[str], bool]] = None,
    ) -> None:
        """Store the production service and process dependencies for a single-run paint process."""
        super().__init__(
            process_id=ProcessID.MAIN_PROCESS,
            messaging=messaging,
            system_manager=system_manager,
            requirements=requirements or ProcessRequirements.none(),
            service_checker=service_checker,
        )
        self._production_service = production_service
        self._robot_service = robot_service
        self._vacuum_pump = vacuum_pump
        self._paint_process_config_service = paint_process_config_service
        self._thread: Optional[threading.Thread] = None
        self._stop_thread: Optional[threading.Thread] = None
        self._stopping = False
        self._manual_single_cycle_requested = False
        self._retry_unmatched_workpiece_requested = False
        self._adjustment_session: PaintAdjustmentSession | None = None
        self._pending_adjustment_session: PaintAdjustmentSession | None = None

    def start_adjustment_cycle(self) -> bool:
        """Start one operator-paced cycle without changing production settings."""
        with self._lock:
            if self._state not in (ProcessState.IDLE, ProcessState.STOPPED):
                return False
            previous_thread = self._thread
            session = PaintAdjustmentSession()
            self._pending_adjustment_session = session
            try:
                self._transition(ProcessState.RUNNING, self._on_start)
            finally:
                self._pending_adjustment_session = None
            started = self._thread is not previous_thread and self._state == ProcessState.RUNNING
            return started

    def paint_next_adjustment_section(self, step: AdjustmentStep) -> bool:
        session = self._adjustment_session
        return bool(
            self.state == ProcessState.RUNNING
            and session is not None
            and session.request_next(step)
        )

    def finish_adjustment_cycle(self) -> bool:
        session = self._adjustment_session
        return bool(
            self.state == ProcessState.RUNNING
            and session is not None
            and session.request_finish()
        )

    def adjustment_status(self) -> tuple[str, float, float]:
        session = self._adjustment_session
        return session.snapshot() if session is not None else ("idle", 0.0, 0.0)

    def start_manual_single_cycle(self) -> bool:
        """Start one calibration-table paint cycle through the normal process state machine."""
        with self._lock:
            if self._state not in (ProcessState.IDLE, ProcessState.STOPPED):
                return False
            previous_thread = self._thread
            self._manual_single_cycle_requested = True
            try:
                self._transition(ProcessState.RUNNING, self._on_start)
            finally:
                self._manual_single_cycle_requested = False
            return self._thread is not previous_thread and self._state == ProcessState.RUNNING

    def retry_unmatched_workpiece(self) -> bool:
        """Restart at paint capture only after an unmatched-workpiece error."""
        with self._lock:
            if (
                self._state != ProcessState.ERROR
                or not self._production_service.can_retry_unmatched_workpiece()
            ):
                return False
            self._transition(ProcessState.IDLE, self._on_reset_errors)
            if self._state != ProcessState.IDLE:
                return False
            self._retry_unmatched_workpiece_requested = True
            try:
                self._transition(ProcessState.RUNNING, self._on_start)
            finally:
                self._retry_unmatched_workpiece_requested = False
            return self._state == ProcessState.RUNNING

    def _on_start(self) -> None:
        """Start the background worker thread that performs one production cycle."""
        self._stopping = False
        self._adjustment_session = self._pending_adjustment_session
        self._thread = threading.Thread(
            target=self._run_in_background,
            args=(
                self._manual_single_cycle_requested,
                self._pending_adjustment_session,
                self._retry_unmatched_workpiece_requested,
            ),
            daemon=True,
            name="PaintProcess",
        )
        self._thread.start()

    def _on_stop(self) -> None:
        """Signal stop and request hardware halt without blocking the process lock."""
        self._stopping = True
        self._production_service.stop_current_phase()
        self._request_hardware_stop()

    def _request_hardware_stop(self) -> None:
        thread = threading.Thread(
            target=self._stop_hardware,
            daemon=True,
            name="PaintProcessStop",
        )
        self._stop_thread = thread
        thread.start()

    def _stop_hardware(self) -> None:
        if self._robot_service is not None:
            try:
                self._robot_service.stop_motion()
            except Exception:
                self._logger.exception("Paint stop failed to stop robot motion")
        if self._vacuum_pump is not None and self._is_vacuum_enabled():
            try:
                self._vacuum_pump.turn_off()
            except Exception:
                self._logger.exception("Paint stop failed to turn vacuum pump off")

    def _is_vacuum_enabled(self) -> bool:
        service = self._paint_process_config_service
        if service is None:
            return bool(PAINT_PROCESS_CONFIG.enable_vacuum_pump)
        try:
            return bool(service.get_snapshot().enable_vacuum_pump)
        except Exception:
            self._logger.exception("Paint stop failed to read vacuum pump setting")
            return bool(PAINT_PROCESS_CONFIG.enable_vacuum_pump)

    def _on_pause(self) -> None:
        """Pause the current cooperative Paint phase."""
        self._production_service.pause_current_phase()

    def _on_resume(self) -> None:
        """Resume the current cooperative Paint phase."""
        self._production_service.resume_current_phase()

    def _on_reset_errors(self) -> None:
        """Clear the internal stop flag so a new run can be started after an error reset."""
        self._stopping = False

    def _run_in_background(
        self,
        manual_single_cycle: bool = False,
        adjustment_session: PaintAdjustmentSession | None = None,
        retry_unmatched_workpiece: bool = False,
    ) -> None:
        """Execute one production cycle and translate the result into process state transitions."""
        try:
            if retry_unmatched_workpiece:
                success, msg = self._production_service.run_once(
                    lambda: self._stopping, retry_unmatched_workpiece=True
                )
            elif adjustment_session is not None:
                success, msg = self._production_service.run_once(
                    lambda: self._stopping, adjustment_session=adjustment_session
                )
            elif manual_single_cycle:
                success, msg = self._production_service.run_once(
                    lambda: self._stopping, manual_single_cycle=True
                )
            else:
                success, msg = self._production_service.run_once(lambda: self._stopping)
        except Exception as exc:
            self._logger.exception("Paint process failed")
            if not self._stopping:
                self.set_error(str(exc))
            return

        if self._stopping:
            return

        if success:
            self._logger.info("Paint process completed: %s", msg)
            self.stop(msg if self._is_no_workpiece_message(msg) else "")
        else:
            self._logger.error("Paint process failed: %s", msg)
            self.set_error(msg)

    @staticmethod
    def _is_no_workpiece_message(message: str) -> bool:
        lowered = str(message or "").strip().lower()
        return (
            "no workpiece" in lowered
            or "no usable contour detected" in lowered
            or "magazine empty" in lowered
            or "magazines are empty" in lowered
        )

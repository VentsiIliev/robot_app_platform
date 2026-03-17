from __future__ import annotations
import threading
from typing import Callable, List, Optional, Tuple

from src.engine.process.executable_state_machine import StateMachineSnapshot
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.hardware.generator.interfaces.i_generator_controller import IGeneratorController
from src.engine.hardware.motor.interfaces.i_motor_service import IMotorService
from src.engine.process.base_process import BaseProcess
from src.engine.process.process_requirements import ProcessRequirements
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.robot_systems.glue.navigation import GlueNavigationService
from src.robot_systems.glue.process_ids import ProcessID
from src.robot_systems.glue.processes.glue_dispensing.dispensing_config import GlueDispensingConfig
from src.robot_systems.glue.processes.glue_dispensing.dispensing_context import DispensingContext
from src.robot_systems.glue.processes.glue_dispensing.dispensing_machine_factory import DispensingMachineFactory
from src.robot_systems.glue.processes.glue_dispensing.dispensing_path import (
    DispensingPathEntry,
    normalize_dispensing_paths,
)
from src.robot_systems.glue.processes.glue_dispensing.glue_pump_controller import GluePumpController
from src.robot_systems.glue.processes.glue_dispensing.i_glue_type_resolver import IGlueTypeResolver
from src.engine.system import ISystemManager
from src.shared_contracts.events.glue_process_events import GlueProcessTopics
from src.shared_contracts.events.process_events import ProcessState


class GlueProcess(BaseProcess):

    def __init__(
        self,
        robot_service:      IRobotService,
        motor_service:      IMotorService,
        resolver:           IGlueTypeResolver,
        config:             GlueDispensingConfig,
        navigation_service: GlueNavigationService,
        messaging:          IMessagingService,
        generator:          Optional[IGeneratorController] = None,
        system_manager:     Optional[ISystemManager]       = None,
        requirements:       Optional[ProcessRequirements]  = None,
        service_checker:    Optional[Callable[[str], bool]] = None,
    ):
        super().__init__(
            process_id      = ProcessID.GLUE,
            messaging       = messaging,
            system_manager  = system_manager,
            requirements    = requirements,
            service_checker = service_checker,
        )
        self._robot             = robot_service
        self._motor_service     = motor_service
        self._generator         = generator
        self._resolver          = resolver
        self._config            = config
        self.navigation_service = navigation_service

        self._paths:         Optional[list[DispensingPathEntry]] = None
        self._spray_on:      bool = False
        self._context:       Optional[DispensingContext] = None
        self._machine = None
        self._worker_thread: Optional[threading.Thread] = None
        self._manual_mode: bool = False

    # ── Public pre-start setter ───────────────────────────────────────

    def set_paths(self, paths: List[Tuple], spray_on: bool) -> None:
        self._paths    = normalize_dispensing_paths(paths)
        self._spray_on = spray_on

    def set_manual_mode(self, enabled: bool) -> None:
        self._manual_mode = bool(enabled)

    def is_manual_mode_enabled(self) -> bool:
        return self._manual_mode

    def step_once(self) -> dict:
        with self._lock:
            if not self._manual_mode:
                raise RuntimeError("Manual mode is disabled")
            if self.state != ProcessState.RUNNING:
                raise RuntimeError("GlueProcess must be running to step manually")
            if self._machine is None or self._context is None:
                raise RuntimeError("GlueProcess has not been started")
            progressed = self._machine.step()
            snapshot = self._publish_diagnostics()
            snapshot["step_result"] = progressed
            return snapshot

    def get_dispensing_snapshot(self) -> dict:
        return {
            "process_state": self.state.value,
            "manual_mode": self._manual_mode,
            "worker_alive": bool(self._worker_thread and self._worker_thread.is_alive()),
            "machine": self._serialize_machine_snapshot(),
            "dispensing": (
                self._context.build_debug_snapshot()
                if self._context is not None else None
            ),
        }

    # ── BaseProcess hooks (called while lock is held — must be fast) ──

    def _on_start(self) -> None:
        if not self._paths:
            self._logger.warning("GlueProcess started without paths — nothing to do")
            return

        ctx = DispensingContext()
        ctx.stop_event.clear()
        ctx.run_allowed.set()

        ctx.motor_service       = self._motor_service
        ctx.generator           = self._generator
        ctx.robot_service       = self._robot
        ctx.resolver            = self._resolver
        ctx.paths               = self._paths
        ctx.spray_on            = self._spray_on
        ctx.robot_tool          = self._config.robot_tool
        ctx.robot_user          = self._config.robot_user
        ctx.global_velocity     = self._config.global_velocity
        ctx.global_acceleration = self._config.global_acceleration
        ctx.use_segment_motion_settings = self._config.use_segment_motion_settings
        ctx.move_to_first_point_poll_s = self._config.move_to_first_point_poll_s
        ctx.move_to_first_point_timeout_s = self._config.move_to_first_point_timeout_s
        ctx.pump_thread_wait_poll_s = self._config.pump_thread_wait_poll_s
        ctx.final_position_poll_s = self._config.final_position_poll_s
        ctx.pump_ready_timeout_s = self._config.pump_ready_timeout_s
        ctx.pump_thread_join_timeout_s = self._config.pump_thread_join_timeout_s
        ctx.pump_adjuster_poll_s = self._config.pump_adjuster_poll_s
        ctx.pump_controller     = GluePumpController(
            self._motor_service,
            use_segment_settings=self._config.use_segment_settings,
        )

        machine = DispensingMachineFactory().build(ctx, self._config)
        self._context = ctx
        self._machine = machine

        if self._manual_mode:
            machine.reset()
            self._worker_thread = None
        else:
            self._worker_thread = threading.Thread(
                target=self._run_machine_until_completion,
                daemon=True,
                name="GlueDispensingMachine",
            )
            self._worker_thread.start()
        self._publish_diagnostics()
        self._logger.info("GlueProcess started (%s paths, spray_on=%s)", len(self._paths), self._spray_on)

    def _on_pause(self) -> None:
        ctx = self._context
        if ctx is None:
            try:
                self._robot.stop_motion()
            except Exception:
                self._logger.exception("stop_motion failed in _on_pause")
            return

        ctx.run_allowed.clear()
        ctx.cleanup.shutdown_best_effort()

        self._publish_diagnostics()
        self._logger.info("GlueProcess paused")

    def _on_resume(self) -> None:
        ctx = self._context
        if ctx is None:
            return
        ctx.is_resuming = True
        ctx.run_allowed.set()
        self._publish_diagnostics()
        self._logger.info("GlueProcess resumed")

    def _on_stop(self) -> None:
        ctx = self._context
        if ctx is not None:
            ctx.stop_event.set()
            ctx.run_allowed.set()          # unblock handle_paused if waiting

        if ctx is None:
            self._robot.stop_motion()
        else:
            ctx.cleanup.shutdown_best_effort()

        self._publish_diagnostics()
        self._logger.info("GlueProcess stopped")

    def _on_reset_errors(self) -> None:
        if self._context is not None:
            self._context.clear_error()
        self._publish_diagnostics()
        self._logger.info("GlueProcess errors reset")

    def _serialize_machine_snapshot(self) -> dict | None:
        if self._machine is None:
            return None
        return self._state_machine_snapshot_to_dict(self._machine.get_snapshot())

    def _state_machine_snapshot_to_dict(self, snapshot: StateMachineSnapshot) -> dict:
        return {
            "initial_state": getattr(snapshot.initial_state, "name", snapshot.initial_state),
            "current_state": getattr(snapshot.current_state, "name", snapshot.current_state),
            "is_running": snapshot.is_running,
            "step_count": snapshot.step_count,
            "last_state": getattr(snapshot.last_state, "name", snapshot.last_state),
            "last_next_state": getattr(snapshot.last_next_state, "name", snapshot.last_next_state),
            "last_error": snapshot.last_error,
        }

    def _publish_diagnostics(self) -> dict:
        snapshot = self.get_dispensing_snapshot()
        try:
            self._messaging.publish(GlueProcessTopics.DIAGNOSTICS, snapshot)
        except Exception:
            self._logger.exception("Failed to publish glue diagnostics")
        return snapshot

    def _run_machine_until_completion(self) -> None:
        machine = self._machine
        if machine is None:
            return

        machine.start_execution()

        with self._lock:
            self._worker_thread = None

            if self._state != ProcessState.RUNNING:
                self._publish_diagnostics()
                return

            snapshot = machine.get_snapshot()
            current_state = getattr(snapshot.current_state, "name", snapshot.current_state)

            if current_state == "IDLE" and snapshot.last_error is None:
                self._transition(ProcessState.STOPPED, self._on_stop)
            elif snapshot.last_error is not None:
                self.set_error(snapshot.last_error)
            else:
                self._publish_diagnostics()

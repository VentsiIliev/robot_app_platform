from __future__ import annotations
import threading
from typing import Callable, List, Optional, Tuple

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
from src.robot_systems.glue.processes.glue_dispensing.glue_pump_controller import GluePumpController
from src.robot_systems.glue.processes.glue_dispensing.i_glue_type_resolver import IGlueTypeResolver
from src.engine.system import ISystemManager


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

        self._paths:         Optional[List[Tuple]] = None
        self._spray_on:      bool = False
        self._context:       Optional[DispensingContext] = None
        self._worker_thread: Optional[threading.Thread] = None

    # ── Public pre-start setter ───────────────────────────────────────

    def set_paths(self, paths: List[Tuple], spray_on: bool) -> None:
        self._paths    = paths
        self._spray_on = spray_on

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
        ctx.pump_controller     = GluePumpController(
            self._motor_service,
            use_segment_settings=self._config.use_segment_settings,
        )

        machine = DispensingMachineFactory().build(ctx, self._config)
        self._context = ctx

        self._worker_thread = threading.Thread(
            target=machine.start_execution,
            daemon=True,
            name="GlueDispensingMachine",
        )
        self._worker_thread.start()
        self._logger.info("GlueProcess started (%s paths, spray_on=%s)", len(self._paths), self._spray_on)

    def _on_pause(self) -> None:
        try:
            self._robot.stop_motion()
        except Exception:
            self._logger.exception("stop_motion failed in _on_pause")

        ctx = self._context
        if ctx is None:
            return

        ctx.run_allowed.clear()

        if ctx.motor_started and ctx.spray_on and ctx.pump_controller:
            addr = ctx.get_motor_address_for_current_path()
            if addr != -1:
                try:
                    ctx.pump_controller.pump_off(addr, ctx.current_settings)
                except Exception:
                    self._logger.exception("pump_off failed in _on_pause")
            ctx.motor_started = False

        if ctx.generator_started and self._generator is not None:
            try:
                self._generator.turn_off()
            except Exception:
                self._logger.exception("generator turn_off failed in _on_pause")
            ctx.generator_started = False

        self._logger.info("GlueProcess paused")

    def _on_resume(self) -> None:
        ctx = self._context
        if ctx is None:
            return
        ctx.is_resuming = True
        ctx.run_allowed.set()
        self._logger.info("GlueProcess resumed")

    def _on_stop(self) -> None:
        ctx = self._context
        if ctx is not None:
            ctx.stop_event.set()
            ctx.run_allowed.set()          # unblock handle_paused if waiting

        try:
            self._robot.stop_motion()
        except Exception:
            self._logger.exception("stop_motion failed in _on_stop")

        if ctx is not None:
            if ctx.motor_started and ctx.spray_on and ctx.pump_controller:
                addr = ctx.get_motor_address_for_current_path()
                if addr != -1:
                    try:
                        ctx.pump_controller.pump_off(addr, ctx.current_settings)
                    except Exception:
                        self._logger.exception("pump_off failed in _on_stop")
                ctx.motor_started = False

            if ctx.generator_started and self._generator is not None:
                try:
                    self._generator.turn_off()
                except Exception:
                    self._logger.exception("generator turn_off failed in _on_stop")
                ctx.generator_started = False

        self._logger.info("GlueProcess stopped")

    def _on_reset_errors(self) -> None:
        self._logger.info("GlueProcess errors reset")

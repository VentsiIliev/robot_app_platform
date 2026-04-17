from __future__ import annotations
import threading
from typing import Callable, Optional

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.engine.process.base_process import BaseProcess
from src.engine.process.process_requirements import ProcessRequirements
from src.engine.robot.height_measuring.i_height_measuring_service import IHeightMeasuringService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.robot.interfaces.i_tool_service import IToolService
from src.engine.robot.targeting import VisionTargetResolver
from src.engine.system.i_system_manager import ISystemManager
from src.robot_systems.glue.domain.matching.i_matching_service import IMatchingService
from src.robot_systems.glue.navigation import GlueNavigationService
from src.robot_systems.glue.component_ids import ProcessID
from src.robot_systems.glue.processes.pick_and_place.config import PickAndPlaceConfig
from src.robot_systems.glue.processes.pick_and_place.workflow import PickAndPlaceWorkflow
from src.engine.robot.plane_pose_mapper import PlanePoseMapper
from src.shared_contracts.events.process_events import ProcessState
from src.shared_contracts.events.pick_and_place_events import PickAndPlaceDiagnosticsEvent, PickAndPlaceTopics


class PickAndPlaceProcess(BaseProcess):

    def __init__(
        self,
        robot_service: IRobotService,
        navigation_service: GlueNavigationService,
        messaging: IMessagingService,
        matching_service: Optional[IMatchingService] = None,
        tool_service: Optional[IToolService] = None,
        height_service: Optional[IHeightMeasuringService] = None,
        resolver: Optional[VisionTargetResolver] = None,
        vacuum_pump: Optional[IVacuumPumpController] = None,
        config: Optional[PickAndPlaceConfig] = None,
        system_manager: Optional[ISystemManager] = None,
        requirements: Optional[ProcessRequirements] = None,
        service_checker: Optional[Callable[[str], bool]] = None,
    ):
        super().__init__(
            process_id=ProcessID.PICK_AND_PLACE,
            messaging=messaging,
            system_manager=system_manager,
            requirements=requirements,
            service_checker=service_checker,
        )
        self._robot      = robot_service
        self._navigation = navigation_service
        self._matching   = matching_service
        self._tools      = tool_service
        self._height     = height_service
        self._resolver   = resolver
        self._vacuum     = vacuum_pump
        self._config     = config or PickAndPlaceConfig()

        self._simulation  = False
        self._run_allowed = threading.Event()
        self._run_allowed.set()
        self._stop_event  = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._step_mode = False
        self._step_budget = 0
        self._waiting_for_step = False
        self._current_checkpoint = ""
        self._step_condition = threading.Condition()

    def set_simulation(self, value: bool) -> None:
        self._simulation = value
        self._logger.info("Simulation mode %s", "ON" if value else "OFF")

    def set_step_mode(self, value: bool) -> None:
        with self._step_condition:
            self._step_mode = bool(value)
            if not self._step_mode:
                self._step_budget = 0
                self._waiting_for_step = False
                self._current_checkpoint = ""
            self._step_condition.notify_all()
        self._publish_diagnostics(
            {
                "last_message": f"Step mode {'enabled' if self._step_mode else 'disabled'}",
            }
        )

    def is_step_mode_enabled(self) -> bool:
        with self._step_condition:
            return self._step_mode

    def step_once(self) -> None:
        with self._step_condition:
            if not self._step_mode:
                raise RuntimeError("Step mode is disabled")
            if self.state != ProcessState.RUNNING:
                raise RuntimeError("PickAndPlaceProcess must be running to step")
            self._step_budget += 1
            self._step_condition.notify_all()
        self._publish_diagnostics({"last_message": "Step requested"})

    # ── BaseProcess hooks (called under lock — non-blocking) ──────────

    def _on_start(self) -> None:
        self._stop_event.clear()
        self._run_allowed.set()
        with self._step_condition:
            self._step_budget = 0
            self._waiting_for_step = False
            self._current_checkpoint = ""
            self._step_condition.notify_all()
        self._robot.enable_robot()
        # Signal visualizer to clear the plane canvas before the new run
        self._messaging.publish(PickAndPlaceTopics.PLANE_RESET, {})
        self._publish_diagnostics(
            {
                "stage": "startup",
                "last_message": "Pick-and-place started",
                "simulation": self._simulation,
            }
        )
        self._worker = threading.Thread(
            target=self._run_workflow, daemon=True, name="PickAndPlaceWorker"
        )
        self._worker.start()
        self._logger.info("Pick-and-place started")

    def _on_stop(self) -> None:
        self._robot.stop_motion()
        self._stop_event.set()
        self._run_allowed.set()   # unblock worker if it is paused
        with self._step_condition:
            self._waiting_for_step = False
            self._current_checkpoint = ""
            self._step_condition.notify_all()
        self._publish_diagnostics({"stage": "cancelled", "last_message": "Pick-and-place stopping"})
        self._logger.info("Pick-and-place stopping")

    def _on_pause(self) -> None:
        self._robot.stop_motion()
        self._run_allowed.clear()
        self._publish_diagnostics({"last_message": "Pick-and-place paused"})
        self._logger.info("Pick-and-place paused")

    def _on_resume(self) -> None:
        self._run_allowed.set()
        self._publish_diagnostics({"last_message": "Pick-and-place resumed"})
        self._logger.info("Pick-and-place resumed")

    def _on_reset_errors(self) -> None:
        self._stop_event.clear()
        self._run_allowed.set()
        with self._step_condition:
            self._step_budget = 0
            self._waiting_for_step = False
            self._current_checkpoint = ""
            self._step_condition.notify_all()
        self._publish_diagnostics({"last_message": "Pick-and-place errors reset", "last_error": None})

    # ── Worker ────────────────────────────────────────────────────────

    def _run_workflow(self) -> None:
        if not all([self._matching, self._tools, self._height, self._resolver, self._vacuum]):
            self._logger.error("Pick-and-place not fully configured")
            self.set_error("Required services not configured")
            return
        try:
            from src.shared_contracts.events.process_events import ProcessState
            from src.shared_contracts.events.pick_and_place_events import WorkpiecePlacedEvent

            from src.shared_contracts.events.pick_and_place_events import MatchedWorkpieceInfo

            def _on_placed(workpiece_name, gripper_id, plane_x, plane_y, width, height):
                self._messaging.publish(
                    PickAndPlaceTopics.WORKPIECE_PLACED,
                    WorkpiecePlacedEvent(
                        workpiece_name=workpiece_name,
                        gripper_id=gripper_id,
                        plane_x=plane_x,
                        plane_y=plane_y,
                        width=width,
                        height=height,
                    ),
                )

            def _on_match_result(workpieces, orientations, no_match_count):
                items = [
                    MatchedWorkpieceInfo(
                        workpiece_name=str(getattr(wp, "name", "?")),
                        workpiece_id=str(getattr(wp, "id", "?")),
                        gripper_id=int(wp.gripperID),
                        orientation=float(orient),
                    )
                    for wp, orient in zip(workpieces, orientations)
                ]
                self._messaging.publish(PickAndPlaceTopics.MATCH_RESULT, items)

            def _on_diagnostics(snapshot):
                self._publish_diagnostics(snapshot)

            calibration_position = self._navigation.get_group_position("CALIBRATION")
            home_position = self._navigation.get_group_position("HOME")
            mapper = None
            if calibration_position is not None and home_position is not None:
                mapper = PlanePoseMapper.from_positions(
                    source_position=calibration_position,
                    target_position=home_position,
                )
            else:
                self._logger.warning(
                    "Calibration-to-pickup mapper unavailable: calibration=%s home=%s",
                    calibration_position,
                    home_position,
                )

            workflow = PickAndPlaceWorkflow(
                robot=self._robot,
                navigation=self._navigation,
                matching=self._matching,
                tools=self._tools,
                height=self._height,
                resolver=self._resolver,
                vacuum_pump=self._vacuum,
                config=self._config,
                logger=self._logger,
                on_workpiece_placed=_on_placed,
                on_match_result=_on_match_result,
                on_diagnostics=_on_diagnostics,
                step_gate=self._wait_for_step_checkpoint,
                calibration_to_target_pose_mapper=mapper,
                simulation=self._simulation,
            )
            result = workflow.run(
                stop_event=self._stop_event,
                run_allowed=self._run_allowed,
            )
            if self._stop_event.is_set():
                return
            if result.state == ProcessState.ERROR:
                if result.error is not None:
                    self._logger.error(
                        "Pick-and-place failed [%s/%s]: %s",
                        result.error.stage.value,
                        result.error.code.value,
                        result.error.message,
                    )
                self.set_error(result.message)
            else:
                self.stop()
        except Exception:
            self._logger.exception("Pick-and-place workflow error")
            self.set_error("Unexpected error in pick-and-place workflow")

    def _publish_diagnostics(self, snapshot: dict) -> None:
        payload = dict(snapshot)
        payload["process_state"] = self.state.value
        payload.update(self._build_step_snapshot())
        self._messaging.publish(
            PickAndPlaceTopics.DIAGNOSTICS,
            PickAndPlaceDiagnosticsEvent(snapshot=payload),
        )

    def _build_step_snapshot(self) -> dict:
        with self._step_condition:
            return {
                "step_mode": self._step_mode,
                "step_budget": self._step_budget,
                "waiting_for_step": self._waiting_for_step,
                "current_checkpoint": self._current_checkpoint,
            }

    def _wait_for_step_checkpoint(self, checkpoint: str, snapshot: dict) -> bool:
        self._publish_diagnostics(
            {
                **snapshot,
                "current_checkpoint": checkpoint,
            }
        )
        while not self._stop_event.is_set():
            PickAndPlaceWorkflow._wait(self._run_allowed, self._stop_event)
            if self._stop_event.is_set():
                return False
            with self._step_condition:
                self._current_checkpoint = checkpoint
                if not self._step_mode:
                    self._waiting_for_step = False
                    return True
                if self._step_budget > 0:
                    self._step_budget -= 1
                    self._waiting_for_step = False
                    return True
                self._waiting_for_step = True
            self._publish_diagnostics(
                {
                    **snapshot,
                    "current_checkpoint": checkpoint,
                    "last_message": f"Waiting for step: {checkpoint}",
                }
            )
            with self._step_condition:
                if self._step_mode and self._step_budget == 0 and not self._stop_event.is_set():
                    self._step_condition.wait(timeout=0.05)
        return False

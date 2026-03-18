from __future__ import annotations
import logging
import threading
from typing import Callable, Optional

from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.robot.height_measuring.i_height_measuring_service import IHeightMeasuringService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.robot.interfaces.i_tool_service import IToolService
from src.robot_systems.glue.domain.matching.i_matching_service import IMatchingService
from src.robot_systems.glue.navigation import GlueNavigationService
from src.robot_systems.glue.processes.pick_and_place.config import PickAndPlaceConfig
from src.robot_systems.glue.processes.pick_and_place.context import PickAndPlaceContext
from src.robot_systems.glue.processes.pick_and_place.errors import (
    PickAndPlaceErrorCode,
    PickAndPlaceErrorInfo,
    PickAndPlaceStage,
    PickAndPlaceWorkflowResult,
    WorkpieceProcessResult,
)
from src.robot_systems.glue.processes.pick_and_place.execution import HeightResolutionService, PickAndPlaceMotionExecutor
from src.robot_systems.glue.processes.pick_and_place.plane import Plane, PlaneManagementService
from src.robot_systems.glue.processes.pick_and_place.planning import (
    PickupCalculator,
    PlacementCalculator,
    PlacementStrategy,
    WorkpieceSelectionPolicy,
)
from src.robot_systems.glue.processes.pick_and_place.workflow.handlers import (
    plan_and_execute_placement,
    prepare_workpiece,
    run_matching_cycle,
    run_startup,
    shutdown_workflow,
)


class PickAndPlaceWorkflow:

    def __init__(
        self,
        robot:                IRobotService,
        navigation:           GlueNavigationService,
        matching:             IMatchingService,
        tools:                IToolService,
        height:               IHeightMeasuringService,
        transformer:          ICoordinateTransformer,
        config:               PickAndPlaceConfig,
        logger:               logging.Logger,
        on_workpiece_placed:  Optional[Callable] = None,
        on_match_result:      Optional[Callable] = None,
        on_diagnostics:       Optional[Callable[[dict], None]] = None,
        step_gate:            Optional[Callable[[str, dict], bool]] = None,
        calibration_to_pickup_mapper: Optional[Callable[[float, float], tuple[float, float]]] = None,
        simulation:           bool = False,
    ):
        self._robot              = robot
        self._navigation         = navigation
        self._matching           = matching
        self._tools              = tools
        self._height             = height
        self._transformer        = transformer
        self._config             = config
        self._logger             = logger
        self._on_workpiece_placed = on_workpiece_placed
        self._on_match_result     = on_match_result
        self._on_diagnostics      = on_diagnostics
        self._step_gate           = step_gate
        self._calibration_to_pickup_mapper = calibration_to_pickup_mapper
        self._simulation          = simulation
        self._plane              = Plane(config.plane)
        self._plane_mgr          = PlaneManagementService(self._plane)
        self._pickup_calc        = PickupCalculator(config)
        self._placement_calc     = PlacementCalculator(self._plane_mgr, config)
        self._placement_strategy = PlacementStrategy(self._placement_calc)
        self._selection_policy   = WorkpieceSelectionPolicy()
        self._height_resolution  = HeightResolutionService(config, height, logger)
        self._context            = PickAndPlaceContext(simulation=simulation)
        self._context.update_plane(self._plane)
        self._motion            = PickAndPlaceMotionExecutor(
            robot=robot,
            navigation=navigation,
            tools=tools,
            logger=logger,
            pick_motion=config.pick_motion,
            place_motion=config.place_motion,
            simulation=simulation,
        )
        self._stage = PickAndPlaceStage
        self._error_code = PickAndPlaceErrorCode
        self._publish_diagnostics("Workflow initialized")

    def run(self, stop_event: threading.Event, run_allowed: threading.Event) -> PickAndPlaceWorkflowResult:
        startup_result = run_startup(self)
        if startup_result is not None:
            return startup_result

        while not stop_event.is_set():
            self._wait(run_allowed, stop_event)
            if stop_event.is_set():
                break

            selected, terminal_result = run_matching_cycle(self)
            if terminal_result is not None:
                return terminal_result

            for item in selected:
                self._wait(run_allowed, stop_event)
                if stop_event.is_set():
                    break

                prepared, prep_result = prepare_workpiece(self, item.workpiece, float(item.orientation))
                if prep_result is not None:
                    workpiece_result = prep_result
                else:
                    workpiece_result = plan_and_execute_placement(self, item.workpiece, prepared)
                if stop_event.is_set():
                    break
                if workpiece_result.error is not None:
                    shutdown_workflow(self)
                    error = workpiece_result.error
                    self._context.mark_error(error)
                    self._publish_diagnostics()
                    return PickAndPlaceWorkflowResult.error_result(
                        code=error.code,
                        stage=error.stage,
                        message=error.message,
                        detail=error.detail,
                        recoverable=error.recoverable,
                    )

                if workpiece_result.plane_full:
                    self._logger.info("Plane full — done")
                    self._context.set_stage(PickAndPlaceStage.PLANE, "Plane full")
                    self._publish_diagnostics()
                    shutdown_workflow(self)
                    return PickAndPlaceWorkflowResult.stopped("")
        shutdown_workflow(self)

        if stop_event.is_set():
            return PickAndPlaceWorkflowResult.stopped("")
        return PickAndPlaceWorkflowResult.stopped("")

    @staticmethod
    def _make_error(
        code: PickAndPlaceErrorCode,
        stage: PickAndPlaceStage,
        message: str,
        detail: Optional[str] = None,
        recoverable: bool = False,
    ) -> PickAndPlaceErrorInfo:
        return PickAndPlaceErrorInfo(
            code=code,
            stage=stage,
            message=message,
            detail=detail,
            recoverable=recoverable,
        )

    @staticmethod
    def _wait(run_allowed: threading.Event, stop_event: threading.Event) -> None:
        while not run_allowed.is_set() and not stop_event.is_set():
            run_allowed.wait(timeout=0.05)

    def _publish_diagnostics(self, message: Optional[str] = None) -> None:
        if message:
            self._context.last_message = message
        if self._on_diagnostics is not None:
            try:
                self._on_diagnostics(self._context.snapshot())
            except Exception:
                self._logger.warning("on_diagnostics callback failed", exc_info=True)

    def _checkpoint(self, name: str) -> bool:
        if self._step_gate is None:
            return True
        try:
            return bool(self._step_gate(name, self._context.snapshot()))
        except Exception:
            self._logger.warning("step_gate callback failed", exc_info=True)
            return True

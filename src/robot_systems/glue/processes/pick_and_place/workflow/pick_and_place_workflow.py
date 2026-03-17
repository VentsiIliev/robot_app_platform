from __future__ import annotations
import logging
import threading
from typing import Callable, Optional, Tuple

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
from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour


def _parse_pickup_point(pickup_point) -> Optional[Tuple[float, float]]:
    if pickup_point is None:
        return None
    if isinstance(pickup_point, str):
        try:
            x, y = pickup_point.split(",")
            return float(x), float(y)
        except (ValueError, AttributeError):
            return None
    if isinstance(pickup_point, (list, tuple)) and len(pickup_point) >= 2:
        return float(pickup_point[0]), float(pickup_point[1])
    return None


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
        self._publish_diagnostics("Workflow initialized")

    def run(self, stop_event: threading.Event, run_allowed: threading.Event) -> PickAndPlaceWorkflowResult:
        self._context.set_stage(PickAndPlaceStage.STARTUP, "Moving to home")
        self._publish_diagnostics()
        move_home = self._motion.move_home()
        if not move_home.success:
            self._context.mark_error(move_home.error)
            self._publish_diagnostics()
            return PickAndPlaceWorkflowResult.error_result(
                code=move_home.error.code,
                stage=move_home.error.stage,
                message=move_home.error.message,
                detail=move_home.error.detail,
                recoverable=move_home.error.recoverable,
            )

        while not stop_event.is_set():
            self._wait(run_allowed, stop_event)
            if stop_event.is_set():
                break

            try:
                self._context.match_attempt += 1
                self._context.set_stage(PickAndPlaceStage.MATCHING, "Running contour matching")
                self._publish_diagnostics()
                result, no_match_count, _, _ = self._matching.run_matching()
            except Exception as exc:
                self._logger.exception("Matching failed")
                self._context.mark_error(
                    PickAndPlaceErrorInfo(
                        code=PickAndPlaceErrorCode.MATCHING_FAILED,
                        stage=PickAndPlaceStage.MATCHING,
                        message="Matching failed during pick-and-place",
                        detail=str(exc),
                    )
                )
                self._publish_diagnostics()
                return PickAndPlaceWorkflowResult.error_result(
                    PickAndPlaceErrorCode.MATCHING_FAILED,
                    PickAndPlaceStage.MATCHING,
                    "Matching failed during pick-and-place",
                    detail=str(exc),
                )
            workpieces   = result.get("workpieces", [])
            orientations = result.get("orientations", [])
            selected = self._selection_policy.select(workpieces, orientations)

            if not selected:
                if no_match_count == 0:
                    self._logger.warning("No contours detected — check camera and placement area")
                    self._context.set_stage(PickAndPlaceStage.MATCHING, "No contours detected")
                    self._publish_diagnostics()
                    return PickAndPlaceWorkflowResult.stopped("No workpieces detected")
                self._logger.info("No workpieces matched — done")
                self._context.set_stage(PickAndPlaceStage.MATCHING, "No workpieces matched")
                self._publish_diagnostics()
                return PickAndPlaceWorkflowResult.stopped("No workpieces matched any known template")

            self._logger.info("Matched %d workpiece(s), %d unmatched", len(selected), no_match_count)

            # ── notify observers of matching results ──────────────────
            if self._on_match_result:
                try:
                    self._on_match_result([item.workpiece for item in selected], [item.orientation for item in selected], no_match_count)
                except Exception:
                    self._logger.warning("on_match_result callback failed", exc_info=True)

            for item in selected:
                self._wait(run_allowed, stop_event)
                if stop_event.is_set():
                    break

                workpiece_result = self._process_match(item.workpiece, float(item.orientation))
                if workpiece_result.error is not None:
                    self._drop_gripper_if_held()
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
                    self._drop_gripper_if_held()
                    return PickAndPlaceWorkflowResult.stopped("")
        self._drop_gripper_if_held()

        if stop_event.is_set():
            return PickAndPlaceWorkflowResult.stopped("")
        return PickAndPlaceWorkflowResult.stopped("")

    # ── Single workpiece ──────────────────────────────────────────────

    def _process_match(self, workpiece, orientation: float) -> WorkpieceProcessResult:
        cnt_obj    = Contour(workpiece.get_main_contour())
        gripper_id = workpiece.gripperID

        parsed    = _parse_pickup_point(workpiece.pickupPoint)
        pickup_px = parsed if parsed is not None else cnt_obj.getCentroid()
        self._context.set_current_workpiece(
            workpiece_id=str(getattr(workpiece, "workpieceId", getattr(workpiece, "id", ""))),
            workpiece_name=str(getattr(workpiece, "name", "")),
            gripper_id=int(gripper_id),
            orientation=float(orientation),
            pickup_point_px=(float(pickup_px[0]), float(pickup_px[1])),
        )
        self._context.holding_gripper_id = getattr(self._tools, "current_gripper", None)
        self._publish_diagnostics("Preparing workpiece")

        try:
            self._context.set_stage(PickAndPlaceStage.TRANSFORM, "Transforming pickup point")
            self._publish_diagnostics()
            robot_x, robot_y = self._transformer.transform(pickup_px[0], pickup_px[1])
            self._context.current_pickup_point_robot = (float(robot_x), float(robot_y))
        except Exception as exc:
            self._logger.exception("Failed to transform pickup point")
            error = self._make_error(
                PickAndPlaceErrorCode.TRANSFORM_FAILED,
                PickAndPlaceStage.TRANSFORM,
                "Failed to transform pickup point into robot coordinates",
                detail=str(exc),
            )
            self._context.mark_error(error)
            self._publish_diagnostics()
            return WorkpieceProcessResult.fail(error)

        self._context.set_stage(PickAndPlaceStage.TOOLING, "Ensuring gripper")
        self._publish_diagnostics()
        gripper_result = self._motion.ensure_gripper(gripper_id)
        if not gripper_result.success:
            self._context.mark_error(gripper_result.error)
            self._publish_diagnostics()
            return WorkpieceProcessResult.fail(gripper_result.error)
        self._context.holding_gripper_id = gripper_id

        self._context.set_stage(PickAndPlaceStage.HEIGHT, "Resolving workpiece height")
        self._publish_diagnostics()
        height_result = self._height_resolution.resolve(float(workpiece.height), robot_x, robot_y)
        self._context.active_height_source = height_result.source
        self._context.current_height_mm = height_result.value_mm
        if height_result.error is not None:
            self._context.mark_error(height_result.error)
            self._publish_diagnostics()
            return WorkpieceProcessResult.fail(height_result.error)
        workpiece_height = height_result.value_mm

        pickup_positions = self._pickup_calc.calculate(
            robot_x, robot_y, workpiece_height, gripper_id, orientation
        )

        self._context.set_stage(PickAndPlaceStage.PLANE, "Planning placement")
        self._publish_diagnostics()
        result = self._placement_strategy.plan(cnt_obj, orientation, workpiece_height, gripper_id)
        if not result.success:
            if result.plane_full:
                return WorkpieceProcessResult.skipped_plane_full()
            error = self._make_error(
                PickAndPlaceErrorCode.UNEXPECTED_ERROR,
                PickAndPlaceStage.PLANE,
                result.message or "Failed to calculate placement",
            )
            self._context.mark_error(error)
            self._publish_diagnostics()
            return WorkpieceProcessResult.fail(error)

        self._context.set_stage(PickAndPlaceStage.PICK, "Executing pick")
        self._publish_diagnostics()
        pick_result = self._motion.execute_pick(pickup_positions)
        if not pick_result.success:
            self._context.mark_error(pick_result.error)
            self._publish_diagnostics()
            return WorkpieceProcessResult.fail(pick_result.error)

        self._context.set_stage(PickAndPlaceStage.PLACE, "Executing place")
        self._publish_diagnostics()
        place_result = self._motion.execute_place(result.placement.drop_off_positions)
        if not place_result.success:
            self._context.mark_error(place_result.error)
            self._publish_diagnostics()
            return WorkpieceProcessResult.fail(place_result.error)
        self._plane_mgr.advance_for_next(result.placement.dimensions.width)
        self._context.processed_count += 1
        self._context.update_plane(self._plane)
        self._context.last_error = None
        self._context.last_message = "Workpiece placed"
        self._publish_diagnostics()

        # ── notify live observers ──────────────────────────────────────
        if self._on_workpiece_placed and result.placement:
            dims = result.placement.dimensions
            tgt  = result.placement.target_position
            try:
                self._on_workpiece_placed(
                    workpiece_name=str(getattr(workpiece, "name", "?")),
                    gripper_id=int(gripper_id),
                    plane_x=tgt.x,
                    plane_y=tgt.y,
                    width=dims.width,
                    height=dims.height,
                )
            except Exception:
                self._logger.warning("on_workpiece_placed callback failed", exc_info=True)

        self._context.clear_current_workpiece()
        self._publish_diagnostics()
        return WorkpieceProcessResult.success()

    def _drop_gripper_if_held(self) -> None:
        self._context.set_stage(PickAndPlaceStage.SHUTDOWN, "Dropping held gripper and returning home")
        self._publish_diagnostics()
        result = self._motion.drop_gripper_if_held()
        if not result.success:
            self._context.mark_error(result.error)
            self._publish_diagnostics()
            self._logger.warning("%s", result.error.message)

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

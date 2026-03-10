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
from src.robot_systems.glue.processes.pick_and_place.models import PickupPositions, DropOffPositions
from src.robot_systems.glue.processes.pick_and_place.plane import Plane
from src.robot_systems.glue.processes.pick_and_place.plane_management import PlaneManagementService
from src.robot_systems.glue.processes.pick_and_place.pickup_calculator import PickupCalculator
from src.robot_systems.glue.processes.pick_and_place.placement_calculator import PlacementCalculator
from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour
from src.shared_contracts.events.process_events import ProcessState


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
        on_match_result:      Optional[Callable] = None,    # ← new

    ):
        self._robot              = robot
        self._navigation         = navigation
        self._matching           = matching
        self._tools              = tools
        self._height             = height
        self._transformer        = transformer
        self._config             = config
        self._logger             = logger
        self._on_workpiece_placed = on_workpiece_placed    # ← new
        self._on_match_result     = on_match_result         # ← new
        self._plane              = Plane(config.plane)
        self._plane_mgr          = PlaneManagementService(self._plane)
        self._pickup_calc        = PickupCalculator(config)
        self._placement_calc     = PlacementCalculator(self._plane_mgr, config)

    def run(self, stop_event: threading.Event, run_allowed: threading.Event) -> Tuple[ProcessState, str]:
        if not self._navigation.move_home():
            self._logger.error("Failed to move to home — aborting")
            return ProcessState.ERROR, "Failed to move to home position"

        while not stop_event.is_set():
            self._wait(run_allowed, stop_event)
            if stop_event.is_set():
                break

            result, no_match_count, _, _ = self._matching.run_matching()
            workpieces   = result.get("workpieces", [])
            orientations = result.get("orientations", [])

            if not workpieces:
                if no_match_count == 0:
                    self._logger.warning("No contours detected — check camera and placement area")
                    return ProcessState.ERROR, "No workpieces detected — check camera and placement area"
                self._logger.info("No workpieces matched — done")
                return ProcessState.ERROR, "No workpieces found matching known templates"

            self._logger.info("Matched %d workpiece(s), %d unmatched", len(workpieces), no_match_count)

            # ── notify observers of matching results ──────────────────
            if self._on_match_result:
                try:
                    self._on_match_result(workpieces, orientations, no_match_count)
                except Exception:
                    self._logger.warning("on_match_result callback failed", exc_info=True)

            for workpiece, orientation in zip(workpieces, orientations):
                self._wait(run_allowed, stop_event)
                if stop_event.is_set():
                    break

                placed = self._process_match(workpiece, float(orientation))

                if placed is None:
                    self._drop_gripper_if_held()
                    return ProcessState.ERROR, "Motion or gripper failure — check robot and tool changer"

                if not placed:
                    self._logger.info("Plane full — done")
                    self._drop_gripper_if_held()
                    return ProcessState.STOPPED, ""

        self._drop_gripper_if_held()
        return ProcessState.STOPPED, ""

    # ── Single workpiece ──────────────────────────────────────────────

    def _process_match(self, workpiece, orientation: float) -> Optional[bool]:
        cnt_obj    = Contour(workpiece.get_main_contour())
        gripper_id = workpiece.gripperID

        parsed    = _parse_pickup_point(workpiece.pickupPoint)
        pickup_px = parsed if parsed is not None else cnt_obj.getCentroid()

        robot_x, robot_y = self._transformer.transform(pickup_px[0], pickup_px[1])

        gripper_ok = self._ensure_gripper(gripper_id)
        if gripper_ok is None:
            return None

        measured_z = self._height.measure_at(robot_x, robot_y) if self._height else None
        # FIXME remove when height calibration is ready
        measured_z = 0


        workpiece_height = (
            measured_z + self._config.height_adjustment_mm
            if measured_z is not None
            else float(workpiece.height)
        )

        pickup_positions = self._pickup_calc.calculate(
            robot_x, robot_y, workpiece_height, gripper_id, orientation
        )

        result = self._placement_calc.calculate(cnt_obj, orientation, workpiece_height, gripper_id)
        if not result.success:
            return False if result.plane_full else True

        if not self._execute_pick(pickup_positions):
            return None

        self._execute_place(result.placement.drop_off_positions)
        self._plane_mgr.advance_for_next(result.placement.dimensions.width)

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

        return True

    # ── Robot motion ──────────────────────────────────────────────────

    def _execute_pick(self, positions: PickupPositions) -> bool:
        for pos in [positions.descent, positions.pickup, positions.lift]:
            ok = self._robot.move_linear(
                pos.to_list(), tool=0, user=0,
                velocity=20, acceleration=10, blendR=0, wait_to_reach=True,
            )
            if not ok:
                self._logger.warning("Pick motion failed at %s", pos)
                return False
        return True

    def _execute_place(self, positions: DropOffPositions) -> None:
        for pos in [positions.approach, positions.drop]:
            self._robot.move_linear(
                pos.to_list(), tool=0, user=0,
                velocity=20, acceleration=10, blendR=0, wait_to_reach=True,
            )

    def _ensure_gripper(self, gripper_id: int) -> Optional[bool]:
        if self._tools.current_gripper == gripper_id:
            return True
        if self._tools.current_gripper is not None:
            ok, msg = self._tools.drop_off_gripper(self._tools.current_gripper)
            if not ok:
                self._logger.error("drop_off_gripper failed: %s — aborting", msg)
                return None
        ok, msg = self._tools.pickup_gripper(gripper_id)
        if not ok:
            self._logger.error("pickup_gripper(%d) failed: %s — aborting", gripper_id, msg)
            return None
        return True

    def _drop_gripper_if_held(self) -> None:
        if self._tools.current_gripper is not None:
            self._tools.drop_off_gripper(self._tools.current_gripper)
            self._navigation.move_home()

    @staticmethod
    def _wait(run_allowed: threading.Event, stop_event: threading.Event) -> None:
        while not run_allowed.is_set() and not stop_event.is_set():
            run_allowed.wait(timeout=0.05)
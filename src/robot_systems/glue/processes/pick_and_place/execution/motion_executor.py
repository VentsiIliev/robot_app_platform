from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.robot.interfaces.i_tool_service import IToolService
from src.robot_systems.glue.navigation import GlueNavigationService
from src.robot_systems.glue.processes.pick_and_place.config import MotionProfile
from src.robot_systems.glue.processes.pick_and_place.errors import (
    PickAndPlaceErrorCode,
    PickAndPlaceErrorInfo,
    PickAndPlaceStage,
)
from src.robot_systems.glue.processes.pick_and_place.planning.models import DropOffPositions, PickupPositions


@dataclass(frozen=True)
class MotionExecutionResult:
    success: bool
    error: Optional[PickAndPlaceErrorInfo] = None
    tool_changed: bool = False

    @classmethod
    def ok(cls, tool_changed: bool = False) -> "MotionExecutionResult":
        return cls(success=True, error=None, tool_changed=tool_changed)

    @classmethod
    def fail(
        cls,
        code: PickAndPlaceErrorCode,
        stage: PickAndPlaceStage,
        message: str,
        detail: Optional[str] = None,
        recoverable: bool = False,
    ) -> "MotionExecutionResult":
        return cls(
            success=False,
            error=PickAndPlaceErrorInfo(
                code=code,
                stage=stage,
                message=message,
                detail=detail,
                recoverable=recoverable,
            ),
        )


class PickAndPlaceMotionExecutor:
    def __init__(
        self,
        robot: IRobotService,
        navigation: GlueNavigationService,
        tools: IToolService,
        logger: logging.Logger,
        pick_motion: MotionProfile,
        place_motion: MotionProfile,
        vacuum_pump: Optional[IVacuumPumpController] = None,
        simulation: bool = False,
    ) -> None:
        self._robot = robot
        self._navigation = navigation
        self._tools = tools
        self._logger = logger
        self._pick_motion = pick_motion
        self._place_motion = place_motion
        self._vacuum = vacuum_pump
        self._simulation = simulation

    def _move_linear(
        self,
        pos,
        profile: MotionProfile,
        code: PickAndPlaceErrorCode,
        stage: PickAndPlaceStage,
        message: str,
    ) -> MotionExecutionResult:
        ok = self._robot.move_linear(
            pos.to_list(),
            tool=profile.tool,
            user=profile.user,
            velocity=profile.velocity,
            acceleration=profile.acceleration,
            blendR=profile.blend_radius,
            wait_to_reach=not self._simulation,
        )
        if ok:
            return MotionExecutionResult.ok()
        self._logger.warning("%s at %s", message, pos)
        return MotionExecutionResult.fail(
            code,
            stage,
            message,
            detail=str(pos),
        )

    def move_home(self) -> MotionExecutionResult:
        if self._simulation:
            self._logger.info("[SIM] move_home skipped")
            return MotionExecutionResult.ok()
        if self._navigation.move_home():
            return MotionExecutionResult.ok()
        return MotionExecutionResult.fail(
            PickAndPlaceErrorCode.MOVE_HOME_FAILED,
            PickAndPlaceStage.STARTUP,
            "Failed to move to home position",
        )

    def ensure_gripper(self, gripper_id: int) -> MotionExecutionResult:
        if self._simulation:
            self._logger.info("[SIM] ensure_gripper(%d) skipped", gripper_id)
            return MotionExecutionResult.ok()
        if self._tools.current_gripper == gripper_id:
            return MotionExecutionResult.ok()
        tool_changed = True
        if self._tools.current_gripper is not None:
            ok, msg = self._tools.drop_off_gripper(self._tools.current_gripper)
            if not ok:
                self._logger.error("drop_off_gripper failed: %s — aborting", msg)
                return MotionExecutionResult.fail(
                    PickAndPlaceErrorCode.TOOL_CHANGE_FAILED,
                    PickAndPlaceStage.TOOLING,
                    "Failed to drop current gripper",
                    detail=str(msg),
                )
        ok, msg = self._tools.pickup_gripper(gripper_id)
        if ok:
            return MotionExecutionResult.ok(tool_changed=tool_changed)
        self._logger.error("pickup_gripper(%d) failed: %s — aborting", gripper_id, msg)
        return MotionExecutionResult.fail(
            PickAndPlaceErrorCode.TOOL_CHANGE_FAILED,
            PickAndPlaceStage.TOOLING,
            f"Failed to pick up gripper {gripper_id}",
            detail=str(msg),
        )

    def execute_pick(self, positions: PickupPositions) -> MotionExecutionResult:
        for move in (
            self.execute_pick_descent(positions),
            self.execute_pickup_contact(positions),
            self.execute_pick_lift(positions),
        ):
            if not move.success:
                return move
        return MotionExecutionResult.ok()

    def execute_place(self, positions: DropOffPositions) -> MotionExecutionResult:
        for move in (
            self.execute_place_approach(positions),
            self.execute_place_drop(positions),
        ):
            if not move.success:
                return move
        return MotionExecutionResult.ok()

    def execute_pick_descent(self, positions: PickupPositions) -> MotionExecutionResult:
        return self._move_linear(
            positions.descent,
            self._pick_motion,
            PickAndPlaceErrorCode.PICK_MOTION_FAILED,
            PickAndPlaceStage.PICK,
            "Pick descent failed",
        )

    def execute_pickup_contact(self, positions: PickupPositions) -> MotionExecutionResult:
        result = self._move_linear(
            positions.pickup,
            self._pick_motion,
            PickAndPlaceErrorCode.PICK_MOTION_FAILED,
            PickAndPlaceStage.PICK,
            "Pick contact failed",
        )
        if not result.success or self._simulation:
            return result
        if self._vacuum is None:
            return MotionExecutionResult.fail(
                PickAndPlaceErrorCode.VACUUM_ON_FAILED,
                PickAndPlaceStage.PICK,
                "Vacuum pump is not configured",
            )
        if self._vacuum.turn_on():
            return result
        return MotionExecutionResult.fail(
            PickAndPlaceErrorCode.VACUUM_ON_FAILED,
            PickAndPlaceStage.PICK,
            "Failed to enable vacuum pump at pickup",
        )

    def execute_pick_lift(self, positions: PickupPositions) -> MotionExecutionResult:
        return self._move_linear(
            positions.lift,
            self._pick_motion,
            PickAndPlaceErrorCode.PICK_MOTION_FAILED,
            PickAndPlaceStage.PICK,
            "Pick lift failed",
        )

    def execute_place_approach(self, positions: DropOffPositions) -> MotionExecutionResult:
        return self._move_linear(
            positions.approach,
            self._place_motion,
            PickAndPlaceErrorCode.PLACE_MOTION_FAILED,
            PickAndPlaceStage.PLACE,
            "Place approach failed",
        )

    def execute_place_drop(self, positions: DropOffPositions) -> MotionExecutionResult:
        result = self._move_linear(
            positions.drop,
            self._place_motion,
            PickAndPlaceErrorCode.PLACE_MOTION_FAILED,
            PickAndPlaceStage.PLACE,
            "Place drop failed",
        )
        if not result.success or self._simulation:
            return result
        if self._vacuum is None:
            return MotionExecutionResult.fail(
                PickAndPlaceErrorCode.VACUUM_OFF_FAILED,
                PickAndPlaceStage.PLACE,
                "Vacuum pump is not configured",
            )
        if self._vacuum.turn_off():
            return result
        return MotionExecutionResult.fail(
            PickAndPlaceErrorCode.VACUUM_OFF_FAILED,
            PickAndPlaceStage.PLACE,
            "Failed to disable vacuum pump at placement",
        )

    def move_to_calibration_position(self) -> MotionExecutionResult:
        if self._simulation:
            self._logger.info("[SIM] move_to_calibration_position skipped")
            return MotionExecutionResult.ok()
        if self._navigation.move_to_calibration_position():
            return MotionExecutionResult.ok()
        return MotionExecutionResult.fail(
            PickAndPlaceErrorCode.MOVE_HOME_FAILED,
            PickAndPlaceStage.PLACE,
            "Failed to move to calibration position",
        )

    def drop_gripper_if_held(self) -> MotionExecutionResult:
        if self._simulation:
            self._logger.info("[SIM] drop_gripper_if_held skipped")
            return MotionExecutionResult.ok()
        if self._vacuum is not None:
            self._vacuum.turn_off()
        if self._tools.current_gripper is None:
            return MotionExecutionResult.ok()

        ok, msg = self._tools.drop_off_gripper(self._tools.current_gripper)
        if not ok:
            self._logger.error("drop_off_gripper failed during shutdown: %s", msg)
            return MotionExecutionResult.fail(
                PickAndPlaceErrorCode.DROP_GRIPPER_FAILED,
                PickAndPlaceStage.SHUTDOWN,
                "Failed to drop held gripper",
                detail=str(msg),
                recoverable=True,
            )

        move_home = self.move_home()
        if not move_home.success:
            return MotionExecutionResult.fail(
                PickAndPlaceErrorCode.MOVE_HOME_FAILED,
                PickAndPlaceStage.SHUTDOWN,
                "Failed to return home after dropping gripper",
                detail=move_home.error.detail if move_home.error else None,
                recoverable=True,
            )
        return MotionExecutionResult.ok()

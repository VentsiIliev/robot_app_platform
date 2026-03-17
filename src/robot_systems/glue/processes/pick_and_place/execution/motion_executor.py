from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

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
        simulation: bool = False,
    ) -> None:
        self._robot = robot
        self._navigation = navigation
        self._tools = tools
        self._logger = logger
        self._pick_motion = pick_motion
        self._place_motion = place_motion
        self._simulation = simulation

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
        for pos in [positions.descent, positions.pickup, positions.lift]:
            ok = self._robot.move_linear(
                pos.to_list(),
                tool=self._pick_motion.tool,
                user=self._pick_motion.user,
                velocity=self._pick_motion.velocity,
                acceleration=self._pick_motion.acceleration,
                blendR=self._pick_motion.blend_radius,
                wait_to_reach=not self._simulation,
            )
            if ok:
                continue
            self._logger.warning("Pick motion failed at %s", pos)
            return MotionExecutionResult.fail(
                PickAndPlaceErrorCode.PICK_MOTION_FAILED,
                PickAndPlaceStage.PICK,
                "Pick motion failed",
                detail=str(pos),
            )
        return MotionExecutionResult.ok()

    def execute_place(self, positions: DropOffPositions) -> MotionExecutionResult:
        for pos in [positions.approach, positions.drop]:
            ok = self._robot.move_linear(
                pos.to_list(),
                tool=self._place_motion.tool,
                user=self._place_motion.user,
                velocity=self._place_motion.velocity,
                acceleration=self._place_motion.acceleration,
                blendR=self._place_motion.blend_radius,
                wait_to_reach=not self._simulation,
            )
            if ok:
                continue
            self._logger.warning("Place motion failed at %s", pos)
            return MotionExecutionResult.fail(
                PickAndPlaceErrorCode.PLACE_MOTION_FAILED,
                PickAndPlaceStage.PLACE,
                "Place motion failed",
                detail=str(pos),
            )
        return MotionExecutionResult.ok()

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

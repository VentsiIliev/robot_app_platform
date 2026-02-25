import math
import logging
import time
from typing import List

from ..interfaces.i_motion_service import IMotionService
from ..interfaces.i_robot import IRobot
from ..interfaces.i_safety_checker import ISafetyChecker
from ..enums.axis import RobotAxis, Direction


class MotionService(IMotionService):

    _WAIT_THRESHOLD_MM = 2.0
    _WAIT_DELAY_S = 0.1
    _WAIT_TIMEOUT_S = 10.0

    def __init__(
        self,
        robot: IRobot,
        safety_checker: ISafetyChecker,
        jog_velocity: float = 10.0,
        jog_acceleration: float = 10.0,
    ):
        self._robot = robot
        self._safety = safety_checker
        self._jog_vel = jog_velocity
        self._jog_acc = jog_acceleration
        self._logger = logging.getLogger(self.__class__.__name__)

    def move_ptp(self, position, tool, user, velocity, acceleration, wait_to_reach=False) -> bool:
        if not self._safety.is_within_safety_limits(position):
            self._logger.warning("move_ptp blocked by safety limits: %s", position)
            return False
        try:
            self._logger.debug("move_ptp → pos=%s tool=%s user=%s vel=%s acc=%s", position, tool, user, velocity,
                               acceleration)
            ret = self._robot.move_ptp(position, tool, user, velocity, acceleration)
            success = ret == 0
            if wait_to_reach and success:
                self._wait_for_position(position)
            self._logger.debug("move_ptp ← success=%s", success)
            return success
        except Exception:
            self._logger.exception("move_ptp failed")
            return False

    def move_linear(self, position, tool, user, velocity, acceleration, blendR=0.0, wait_to_reach=False) -> bool:
        if not self._safety.is_within_safety_limits(position):
            self._logger.warning("move_linear blocked by safety limits: %s", position)
            return False
        try:
            self._logger.debug("move_linear → pos=%s tool=%s user=%s vel=%s acc=%s blendR=%s", position, tool, user,
                               velocity, acceleration, blendR)
            ret = self._robot.move_linear(position, tool, user, velocity, acceleration, blendR)
            success = ret == 0
            if wait_to_reach and success:
                self._wait_for_position(position)
            self._logger.debug("move_linear ← success=%s", success)
            return success
        except Exception:
            self._logger.exception("move_linear failed")
            return False

    def start_jog(self, axis: RobotAxis, direction: Direction, step: float) -> int:
        self._logger.debug("start_jog → axis=%s direction=%s step=%s", axis, direction, step)
        try:
            ret = self._robot.start_jog(axis, direction, step, self._jog_vel, self._jog_acc)
            self._logger.debug("start_jog ← ret=%s", ret)
            return ret
        except Exception:
            self._logger.exception("start_jog failed")
            return -1

    def stop_motion(self) -> bool:
        self._logger.debug("stop_motion →")
        try:
            success = self._robot.stop_motion() == 0
            self._logger.debug("stop_motion ← success=%s", success)
            return success
        except Exception:
            self._logger.exception("stop_motion failed")
            return False

    def get_current_position(self) -> List[float]:
        return self._robot.get_current_position()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _wait_for_position(
        self,
        target: List[float],
        threshold: float = _WAIT_THRESHOLD_MM,
        delay: float = _WAIT_DELAY_S,
        timeout: float = _WAIT_TIMEOUT_S,
    ) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = self._robot.get_current_position()
            if current and len(current) >= 3:
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(current[:3], target[:3])))
                if dist <= threshold:
                    return True
            time.sleep(delay)
        self._logger.warning("Timed out waiting for robot to reach %s", target)
        return False


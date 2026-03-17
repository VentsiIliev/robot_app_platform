import math
import logging
import time
from typing import Callable, List, Optional

from ..interfaces.i_motion_service import IMotionService
from ..interfaces.i_robot import IRobot
from ..interfaces.i_safety_checker import ISafetyChecker
from ..enums.axis import RobotAxis, Direction
from src.shared_contracts.events.robot_events import RobotTopics


class MotionService(IMotionService):
    _WAIT_THRESHOLD_MM = 2.0
    _WAIT_DELAY_S = 0.1
    _WAIT_TIMEOUT_S = 10.0
    _STOP_RETRY_DELAY_S = 0.05
    _STOP_ATTEMPTS = 3

    def __init__(
            self,
            robot: IRobot,
            safety_checker: ISafetyChecker,
            jog_velocity: float = 10.0,
            jog_acceleration: float = 10.0,
            messaging_service=None,
    ):
        self._robot = robot
        self._safety = safety_checker
        self._jog_vel = jog_velocity
        self._jog_acc = jog_acceleration
        self._last_jog_target: List[float] = []
        self._logger = logging.getLogger(self.__class__.__name__)
        self._cached_position: List[float] = []
        if messaging_service:
            messaging_service.subscribe(RobotTopics.POSITION, self._on_position)

    def _on_position(self, position: List[float]) -> None:
        self._cached_position = position

    def move_ptp(
            self,
            position,
            tool,
            user,
            velocity,
            acceleration,
            wait_to_reach=False,
            wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        violations = self._safety.get_violations(position)
        if violations:
            self._logger.warning("move_ptp blocked by safety limits: %s", ", ".join(violations))
            return False
        try:
            self._logger.debug("move_ptp → pos=%s tool=%s user=%s vel=%s acc=%s", position, tool, user, velocity,
                               acceleration)
            ret = self._robot.move_ptp(
                position,
                tool,
                user,
                velocity,
                acceleration,
                blocking=wait_to_reach,
            )
            success = ret == 0
            if wait_to_reach and success:
                success = self._wait_for_position(position, cancelled=wait_cancelled)
            self._logger.debug("move_ptp ← success=%s", success)
            return success
        except Exception:
            self._logger.exception("move_ptp failed")
            return False

    def move_linear(
            self,
            position,
            tool,
            user,
            velocity,
            acceleration,
            blendR=0.0,
            wait_to_reach=False,
            wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        violations = self._safety.get_violations(position)
        if violations:
            self._logger.warning("move_ptp blocked by safety limits: %s", ", ".join(violations))
            return False
        try:
            self._logger.debug("move_linear → pos=%s tool=%s user=%s vel=%s acc=%s blendR=%s", position, tool, user,
                               velocity, acceleration, blendR)
            ret = self._robot.move_linear(
                position,
                tool,
                user,
                velocity,
                acceleration,
                blendR,
                blocking=wait_to_reach,
            )
            success = ret == 0
            if wait_to_reach and success:
                success = self._wait_for_position(position, cancelled=wait_cancelled)
            self._logger.debug("move_linear ← success=%s", success)
            return success
        except Exception:
            self._logger.exception("move_linear failed")
            return False

    def start_jog(self, axis: RobotAxis, direction: Direction, step: float) -> int:
        self._logger.debug("start_jog → axis=%s direction=%s step=%s", axis, direction, step)
        try:
            current = self._robot.get_current_position()
            self._logger.info(f"Current -> {current}")
            if current and len(current) >= 3:
                target = list(current)

                idx = axis.value - 1  # X=0, Y=1, Z=2, RX=3, RY=4, RZ=5
                if idx < len(target):
                    if idx < 3 and len(target) >= 6:
                        dx, dy, dz = self._tool_frame_delta(target, idx, direction.value, step)
                        target[0] += dx
                        target[1] += dy
                        target[2] += dz
                    else:
                        target[idx] += direction.value * step
                self._logger.info(f"Target -> {target}")
                violations = self._safety.get_violations(target)
                if violations:
                    self._logger.warning(
                        "start_jog blocked by safety limits: axis=%s dir=%s step=%s → %s",
                        axis, direction, step, ", ".join(violations),
                    )
                    return -1

            ret = self._robot.start_jog(axis, direction, step, self._jog_vel, self._jog_acc)
            self._logger.debug("start_jog ← ret=%s", ret)
            return ret
        except Exception:
            self._logger.exception("start_jog failed")
            return -1

    def stop_motion(self) -> bool:
        self._logger.debug("stop_motion →")
        self._last_jog_target = []
        for attempt in range(1, self._STOP_ATTEMPTS + 1):
            try:
                success = self._robot.stop_motion() == 0
                if success:
                    self._logger.debug("stop_motion ← success=True attempts=%s", attempt)
                    return True
            except Exception:
                self._logger.exception("stop_motion failed")
                return False
            if attempt < self._STOP_ATTEMPTS:
                time.sleep(self._STOP_RETRY_DELAY_S)
        self._logger.debug("stop_motion ← success=False attempts=%s", self._STOP_ATTEMPTS)
        return False

    def get_current_position(self) -> List[float]:
        return self._robot.get_current_position()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tool_frame_delta(position: List[float], axis_idx: int,
                          direction_value: float, step: float):
        """Project a single tool-frame jog step into base-frame XYZ displacement.

        R = Rz(rz) · Ry(ry) · Rx(rx), angles in degrees from position[3:6].
        Returns (dx, dy, dz) in base frame.
        """
        cx, sx = math.cos(math.radians(position[3])), math.sin(math.radians(position[3]))
        cy, sy = math.cos(math.radians(position[4])), math.sin(math.radians(position[4]))
        cz, sz = math.cos(math.radians(position[5])), math.sin(math.radians(position[5]))
        cols = (
            (cy * cz, cy * sz, -sy),  # tool X in base
            (cz * sx * sy - cx * sz, cx * cz + sx * sy * sz, cy * sx),  # tool Y in base
            (cx * cz * sy + sx * sz, cx * sy * sz - cz * sx, cx * cy),  # tool Z in base
        )
        col = cols[axis_idx]
        scale = direction_value * step
        return col[0] * scale, col[1] * scale, col[2] * scale

    def _wait_for_position(
            self,
            target: List[float],
            threshold: float = _WAIT_THRESHOLD_MM,
            delay: float = _WAIT_DELAY_S,
            timeout: float = _WAIT_TIMEOUT_S,
            cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cancelled is not None and cancelled():
                self._logger.debug("wait_for_position cancelled while waiting for %s", target)
                return False
            current = self._cached_position or self._robot.get_current_position()
            if current and len(current) >= 3:
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(current[:3], target[:3])))
                if dist <= threshold:
                    return True
            time.sleep(delay)
        self._logger.warning("Timed out waiting for robot to reach %s", target)
        return False

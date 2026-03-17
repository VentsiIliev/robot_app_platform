import logging
from typing import List, Optional

from ..interfaces.i_robot import IRobot
from ..interfaces.i_motion_service import IMotionService
from ..interfaces.i_robot_service import IRobotService
from ..interfaces.i_robot_state_provider import IRobotStateProvider
from ..interfaces.i_tool_service import IToolService
from ..enums.axis import RobotAxis, Direction


class RobotService(IRobotService):

    def __init__(
        self,
        motion: IMotionService,
        robot: IRobot,
        state_provider: IRobotStateProvider,
        tool_service: Optional[IToolService] = None,
    ):
        self._motion = motion
        self._robot = robot
        self._state = state_provider
        self._tools = tool_service
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def tools(self) -> Optional[IToolService]:
        return self._tools

    # --- IMotionService ---

    def move_ptp(self, position, tool, user, velocity, acceleration, wait_to_reach=False) -> bool:
        return self._motion.move_ptp(position, tool, user, velocity, acceleration, wait_to_reach)

    def move_linear(self, position, tool, user, velocity, acceleration, blendR=0.0, wait_to_reach=False) -> bool:
        return self._motion.move_linear(position, tool, user, velocity, acceleration, blendR, wait_to_reach)

    def start_jog(self, axis: RobotAxis, direction: Direction, step: float) -> int:
        return self._motion.start_jog(axis, direction, step)

    def stop_motion(self) -> bool:
        return self._motion.stop_motion()

    def get_current_position(self) -> List[float]:
        return list(self._state.position)

    # --- IRobotLifecycle ---

    def enable_robot(self) -> None:
        self._robot.enable()

    def disable_robot(self) -> None:
        self._robot.disable()

    # --- IRobotService ---

    def get_current_velocity(self) -> float:
        return self._state.velocity

    def get_current_acceleration(self) -> float:
        return self._state.acceleration

    def get_state(self) -> str:
        return self._state.state

    def get_state_topic(self) -> str:
        return self._state.state_topic

    def execute_trajectory(self, path, rx=180, ry=0, rz=0, vel=0.1, acc=0.1, blocking=False):
        """Send a Cartesian path to the robot driver as a trajectory (not safety-checked)."""
        return self._robot.execute_trajectory(path, rx=rx, ry=ry, rz=rz, vel=vel, acc=acc, blocking=blocking)

    def get_execution_status(self):
        return self._robot.get_execution_status()

    def get_last_trajectory_command_info(self):
        return self._robot.get_last_trajectory_command_info()

from typing import List

from src.engine.robot.enums.axis import RobotAxis, Direction
from src.engine.robot.interfaces.i_robot import IRobot
from .fairino.linux.fairino import Robot
from .test_robot import TestRobotWrapper


class FairinoRobot(IRobot):

    def __init__(self, ip: str):
        self.ip = ip
        #self.robot = TestRobotWrapper()  # Replace with Robot.RPC(self.ip) in production
        self.robot = Robot.RPC(self.ip)
        self._over_speed_strategy = 3

    def move_ptp(
        self,
        position: List[float],
        tool: int,
        user: int,
        vel: float,
        acc: float,
    ) -> int:
        return self.robot.MoveCart(position, tool, user, vel=vel, acc=acc) or 0

    def move_linear(
        self,
        position: List[float],
        tool: int,
        user: int,
        vel: float,
        acc: float,
        blend_radius: float = 0.0,
    ) -> int:
        return self.robot.MoveL(position, tool, user, vel=vel, acc=acc, blendR=blend_radius) or 0

    def start_jog(
        self,
        axis: RobotAxis,
        direction: Direction,
        step: float,
        vel: float,
        acc: float,
    ) -> int:
        return self.robot.StartJOG(
            ref=4, nb=axis.value, dir=direction.value, vel=vel, acc=acc, max_dis=step
        ) or 0

    def stop_motion(self) -> int:
        return self.robot.StopMotion() or 0

    def get_current_position(self) -> List[float]:
        try:
            result = self.robot.GetActualTCPPose()
        except Exception:
            import traceback
            traceback.print_exc()
            return []
        if isinstance(result, int) or result is None:
            return []
        return result[1]

    def get_current_velocity(self) -> float:
        return 0.0

    def get_current_acceleration(self) -> float:
        return 0.0

    def enable(self) -> None:
        self.robot.RobotEnable(1)

    def disable(self) -> None:
        self.robot.RobotEnable(0)

    def execute_trajectory(self, path, rx=180, ry=0, rz=0, vel=0.1, acc=0.1, blocking=False):
        self.robot.execute_path(path, rx=rx, ry=ry, rz=rz, vel=vel, acc=acc, blocking=blocking)

    def reset_all_errors(self) -> int:
        return self.robot.ResetAllError() or 0

    def set_digital_output(self, port_id: int, value: bool) -> None:
        self.robot.SetDO(port_id, value)

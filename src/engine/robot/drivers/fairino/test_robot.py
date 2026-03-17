from typing import List

from src.engine.robot.enums.axis import RobotAxis, Direction
from src.engine.robot.interfaces.i_robot import IRobot


class TestRobotWrapper(IRobot):
    """
       A full mock of the Fairino Robot interface.
       Implements every method used by FairinoRobot and returns safe dummy values.
       """

    def __init__(self):
        print("⚙️  TestRobot initialized (mock robot).")

    # --- Motion commands ---
    def move_ptp(self, position: List[float], tool: int, user: int, vel: float, acc: float, blocking: bool = True) -> int:
        return 0

    def move_linear(
        self, position: List[float], tool: int, user: int,
        vel: float, acc: float, blend_radius: float = 0.0, blocking: bool = True
    ) -> int:
        return 0

    def start_jog(self, axis: RobotAxis, direction: Direction, step: float, vel: float, acc: float) -> int:
        return 0

    def stop_motion(self) -> int:
        return 0

    # --- State queries ---
    def get_current_position(self) -> List[float]:
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def get_current_velocity(self) -> float:
        return 0.0

    def get_current_acceleration(self) -> float:
        return 0.0

    def enable(self) -> None:
        pass

    def disable(self) -> None:
        pass

    # --- Raw SDK stubs (used by FairinoRobot) ---

    def MoveCart(self, position, tool, user, vel, acc):
        return 0

    def MoveL(self, position, tool, user, vel, acc, blendR=0):
        return 0

    def StartJOG(self, ref, nb, dir, vel, acc, max_dis):
        return 0

    def StopMotion(self):
        return 0

    def GetActualTCPPose(self):
        return (0, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    def RobotEnable(self, param):
        pass

    def ResetAllError(self):
        return 0

    def SetDO(self, port_id, value):
        pass

    def execute_path(self, path, rx, ry, rz, vel, acc, blocking):
        pass

    def GetSDKVersion(self):
        return "TestRobot SDK v1.0"

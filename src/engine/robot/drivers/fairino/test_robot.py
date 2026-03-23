from typing import List
import logging
from src.engine.robot.enums.axis import RobotAxis, Direction
from src.engine.robot.interfaces.i_robot import IRobot

_logger = logging.getLogger(__name__)

class TestRobotWrapper(IRobot):
    """
       A full mock of the Fairino Robot interface.
       Implements every method used by FairinoRobot and returns safe dummy values.
       """

    def execute_trajectory(self, path, rx: float = 180, ry: float = 0, rz: float = 0, vel: float = 0.1,
                           acc: float = 0.1, blocking: bool = False) -> None:
        _logger.debug(f"TestRobot: execute_trajectory called with {len(path)} points, rx={rx}, ry={ry}, rz={rz}, vel={vel}, acc={acc}, blocking={blocking}")

    def __init__(self):
        _logger.info("TestRobot initialized")
    # --- Motion commands ---
    def move_ptp(self, position: List[float], tool: int, user: int, vel: float, acc: float, blocking: bool = True) -> int:
        _logger.debug(f"TestRobot: move_ptp called with {len(position)} points, vel={vel}, acc={acc}, blocking={blocking}")
        return 0

    def move_linear(
        self, position: List[float], tool: int, user: int,
        vel: float, acc: float, blend_radius: float = 0.0, blocking: bool = True
    ) -> int:
        _logger.debug(f"TestRobot: move_linear called with {len(position)} points, vel={vel}, acc={acc}, blend_radius={blend_radius}, blocking={blocking}")
        return 0

    def start_jog(self, axis: RobotAxis, direction: Direction, step: float, vel: float, acc: float) -> int:
        _logger.debug(f"TestRobot: start_jog called with axis={axis}, direction={direction}, step={step}, vel={vel}, acc={acc}")
        return 0

    def stop_motion(self) -> int:
        _logger.debug("TestRobot: stop_motion called")
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


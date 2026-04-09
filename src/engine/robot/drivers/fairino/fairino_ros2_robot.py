import logging
import math
from typing import List

from src.engine.robot.enums.axis import RobotAxis, Direction
from src.engine.robot.interfaces.i_robot import IRobot
from .fairino_ros2_client import FairinoRos2Client

logger = logging.getLogger(__name__)


class FairinoRos2Robot(IRobot):

    def __init__(self, server_url: str):
        logger.info("FairinoRos2Robot init — server_url=%s", server_url)
        self._client = FairinoRos2Client(server_url=server_url)
        logger.info("FairinoRos2Robot ready")

    def move_ptp(self, position: List[float], tool: int, user: int, vel: float, acc: float, blocking: bool = True) -> int:
        logger.debug("move_ptp → pos=%s tool=%s user=%s vel=%s acc=%s", position, tool, user, vel, acc)
        # Calling move_liner here is intentional !!!
        ret = self._client.move_liner(position, tool, user, vel, acc, blocking=blocking) or 0
        logger.debug("move_ptp ← raw_ret=%s normalised=%s accepted=%s", ret, ret, ret >= 0)
        return ret

    def move_linear(self, position: List[float], tool: int, user: int, vel: float, acc: float, blend_radius: float = 0.0, blocking: bool = True) -> int:
        logger.debug("move_linear → pos=%s tool=%s user=%s vel=%s acc=%s blend=%s", position, tool, user, vel, acc, blend_radius)
        ret = self._client.move_liner(position, tool, user, vel, acc, blend_radius, blocking=blocking) or 0
        logger.debug("move_linear ← raw_ret=%s accepted=%s", ret, ret >= 0)
        return ret

    def start_jog(self, axis: RobotAxis, direction: Direction, step: float, vel: float, acc: float) -> int:
        logger.debug("start_jog → axis=%s direction=%s step=%s vel=%s acc=%s", axis, direction, step, vel, acc)
        ret = self._client.start_jog(axis, direction, step, vel, acc) or 0
        logger.debug("start_jog ← raw_ret=%s success=%s", ret, ret == 0)
        return ret

    def stop_motion(self) -> int:
        logger.debug("stop_motion →")
        ret = self._client.stop_motion() or 0
        logger.debug("stop_motion ← raw_ret=%s success=%s", ret, ret == 0)
        return ret

    def get_current_position(self) -> List[float]:
        # logger.debug("get_current_position →")
        result = self._client.get_current_position()
        position = result if result is not None else []
        # logger.debug("get_current_position ← raw=%s resolved=%s", result, position)
        return position

    def get_current_velocity(self) -> float:
        # logger.debug("get_current_velocity →")
        result = self._client.get_current_velocity()
        if result is None:
            logger.debug("get_current_velocity ← no data, returning 0.0")
            return 0.0
        _, components = result
        magnitude = math.sqrt(sum(v ** 2 for v in components))
        # logger.debug("get_current_velocity ← components=%s magnitude=%s", components, magnitude)
        return magnitude

    def get_current_acceleration(self) -> float:
        return 0.0

    def get_execution_status(self):
        return self._client.get_status()

    def get_last_trajectory_command_info(self):
        return self._client.get_last_execute_path_response()

    def get_connection_state(self) -> str:
        return self._client.get_connection_state()

    def get_connection_details(self) -> dict:
        return self._client.get_connection_details()

    def enable_safety_walls(self) -> bool:
        logger.info("enable_safety_walls →")
        success = self._client.enable_safety_walls()
        logger.info("enable_safety_walls ← success=%s", success)
        return success

    def disable_safety_walls(self) -> bool:
        logger.info("disable_safety_walls →")
        success = self._client.disable_safety_walls()
        logger.info("disable_safety_walls ← success=%s", success)
        return success

    def are_safety_walls_enabled(self):
        return self._client.are_safety_walls_enabled()

    def get_safety_walls_status(self) -> dict:
        return self._client.get_safety_walls_status()

    def validate_pose(
        self,
        start_position,
        target_position,
        tool: int = 0,
        user: int = 0,
        start_joint_state: dict | None = None,
    ) -> dict:
        return self._client.validate_pose(
            start_position,
            target_position,
            tool=tool,
            user=user,
            start_joint_state=start_joint_state,
        )

    def enable(self) -> None:
        logger.info("enable →")
        self._client.enable()
        logger.info("enable ← done")

    def disable(self) -> None:
        logger.info("disable →")
        self._client.disable()
        logger.info("disable ← done")

    def execute_trajectory(
        self,
        path,
        rx=180,
        ry=0,
        rz=0,
        vel=0.1,
        acc=0.1,
        blocking=False,
        orientation_mode: str = "constant",
    ):
        logger.debug(
            "execute_trajectory → waypoints=%d rx_degrees=%s ry_degrees=%s rz_degrees=%s vel=%s acc=%s blocking=%s orientation_mode=%s",
            len(path) if path else 0, rx, ry, rz, vel, acc, blocking, orientation_mode)
        self._client.execute_path(
            path,
            rx=rx,
            ry=ry,
            rz=rz,
            vel=vel,
            acc=acc,
            blocking=blocking,
            orientation_mode=orientation_mode,
        )
        logger.debug("execute_trajectory ← done")

    def reset_all_errors(self) -> int:
        logger.info("reset_all_errors →")
        ret = self._client.resetAllErrors() or 0
        logger.info("reset_all_errors ← ret=%s", ret)
        return ret

    def set_digital_output(self, port_id: int, value: bool) -> None:
        logger.debug("set_digital_output → port=%s value=%s", port_id, value)
        self._client.setDigitalOutput(port_id, int(value))
        logger.debug("set_digital_output ← done")

    # OVERRIDE CLONE TO THE ROBOT STATE MANAGE USE SEPARATE CONNECTION
    def clone(self) -> 'IRobot':
        return FairinoRos2Robot(server_url=self._client.server_url)

    def prefers_incremental_jog(self) -> bool:
        return True

import logging
from typing import List, Optional

from ..interfaces.i_robot import IRobot
from ..interfaces.i_motion_service import IMotionService
from ..interfaces.i_robot_service import IRobotService
from ..interfaces.i_robot_state_provider import IRobotStateProvider
from ..interfaces.i_tool_service import IToolService
from ..enums.axis import RobotAxis, Direction
from ..motion_sequence import MotionSequenceSegment


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

    def stop(self) -> None:
        stop_monitoring = getattr(self._state, "stop_monitoring", None)
        if callable(stop_monitoring):
            stop_monitoring()

    # --- IMotionService ---

    def move_ptp(self, position, tool, user, velocity, acceleration, wait_to_reach=False) -> bool:
        return self._motion.move_ptp(position, tool, user, velocity, acceleration, wait_to_reach)

    def move_linear(self, position, tool, user, velocity, acceleration, blendR=0.0, wait_to_reach=False) -> bool:
        return self._motion.move_linear(position, tool, user, velocity, acceleration, blendR, wait_to_reach)

    def move_sequence(
        self,
        segments: List[MotionSequenceSegment],
        tool: int,
        user: int,
        wait_to_reach=False,
    ) -> bool:
        return self._motion.move_sequence(segments, tool, user, wait_to_reach)

    def move_custom_sequence(
        self,
        segments: List[MotionSequenceSegment],
        tool: int,
        user: int,
        wait_to_reach=False,
    ) -> bool:
        return self._motion.move_custom_sequence(segments, tool, user, wait_to_reach)

    def start_jog(
        self,
        axis: RobotAxis,
        direction: Direction,
        step: float,
        velocity: float | None = None,
        acceleration: float | None = None,
    ) -> int:
        return self._motion.start_jog(axis, direction, step, velocity=velocity, acceleration=acceleration)

    def start_servo_jog(
        self,
        axis: RobotAxis,
        direction: Direction,
        linear_mm_s: float | None = None,
        angular_deg_s: float | None = None,
        *,
        frame: str | int = "user",
        tool: int = 0,
        user: int = 0,
    ) -> int:
        starter = getattr(self._motion, "start_servo_jog", None)
        if not callable(starter):
            return -1
        return starter(
            axis,
            direction,
            linear_mm_s=linear_mm_s,
            angular_deg_s=angular_deg_s,
            frame=frame,
            tool=tool,
            user=user,
        )

    def start_joint_jog(
        self,
        joint: str,
        direction: Direction,
        step: float,
        velocity: float | None = None,
        acceleration: float | None = None,
    ) -> int:
        starter = getattr(self._motion, "start_joint_jog", None)
        if not callable(starter):
            return -1
        return starter(
            joint,
            direction,
            step,
            velocity=velocity,
            acceleration=acceleration,
        )

    def stop_servo_jog(self) -> int:
        stopper = getattr(self._motion, "stop_servo_jog", None)
        if not callable(stopper):
            return -1
        return stopper()

    def stop_motion(self) -> bool:
        return self._motion.stop_motion()

    def get_current_position(self) -> List[float]:
        return list(self._state.position)

    def get_current_flange_position(self) -> List[float]:
        return self._robot.get_current_flange_position()

    def set_active_tool(self, tool: int) -> bool:
        try:
            ok = bool(self._robot.set_active_tool(int(tool)))
        except Exception:
            self._logger.exception("set_active_tool failed for tool=%s", tool)
            return False
        if ok:
            refresh = getattr(self._state, "refresh_once", None)
            if callable(refresh):
                try:
                    refresh()
                except Exception:
                    self._logger.warning("State refresh after set_active_tool failed", exc_info=True)
        return ok

    def set_active_workobject(self, user: int) -> bool:
        setter = getattr(self._robot, "set_active_workobject", None)
        if not callable(setter):
            return False
        try:
            ok = bool(setter(int(user)))
        except Exception:
            self._logger.exception("set_active_workobject failed for user=%s", user)
            return False
        if ok:
            refresh = getattr(self._state, "refresh_once", None)
            if callable(refresh):
                try:
                    refresh()
                except Exception:
                    self._logger.warning("State refresh after set_active_workobject failed", exc_info=True)
        return ok

    def get_workobject_registry(self):
        getter = getattr(self._robot, "get_workobject_registry", None)
        return getter() if callable(getter) else None

    def update_workobject_registry(self, user_id, name=None, transform=None, persist=False):
        updater = getattr(self._robot, "update_workobject_registry", None)
        if not callable(updater):
            return -1
        return updater(user_id, name=name, transform=transform, persist=persist)

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

    def get_connection_state(self) -> str:
        getter = getattr(self._robot, "get_connection_state", None)
        if callable(getter):
            try:
                return str(getter() or self.get_state())
            except Exception:
                self._logger.debug("get_connection_state failed", exc_info=True)
                return "disconnected"
        return self.get_state()

    def get_connection_details(self) -> dict:
        getter = getattr(self._robot, "get_connection_details", None)
        if callable(getter):
            try:
                details = getter() or {}
            except Exception:
                self._logger.debug("get_connection_details failed", exc_info=True)
                return {"state": "disconnected"}
            return dict(details) if isinstance(details, dict) else {}
        return {}

    def get_drive_status(self) -> dict:
        getter = getattr(self._robot, "get_drive_status", None)
        if callable(getter):
            try:
                status = getter() or {}
            except Exception:
                self._logger.debug("get_drive_status failed", exc_info=True)
                return {"success": False}
            return dict(status) if isinstance(status, dict) else {}
        return {}

    def get_state_topic(self) -> str:
        return self._state.state_topic

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
        """Send a Cartesian path to the robot driver as a trajectory (not safety-checked)."""
        return self._robot.execute_trajectory(
            path,
            rx=rx,
            ry=ry,
            rz=rz,
            vel=vel,
            acc=acc,
            blocking=blocking,
            orientation_mode=orientation_mode,
        )

    def execute_ordered_motion_chain(
        self,
        segments: list[dict],
        tool: int,
        user: int,
        blocking: bool = False,
    ):
        return self._robot.execute_ordered_motion_chain(
            segments,
            tool=tool,
            user=user,
            blocking=blocking,
        )

    def get_execution_status(self):
        return self._robot.get_execution_status()

    def get_last_trajectory_command_info(self):
        return self._robot.get_last_trajectory_command_info()

    def unwind_joint6(
        self,
        blocking: bool = True,
        queue_if_busy: bool = True,
        vel: float | None = None,
        acc: float | None = None,
    ) -> bool:
        try:
            result = self._robot.unwind_joint6(
                blocking=blocking,
                queue_if_busy=queue_if_busy,
                vel=vel,
                acc=acc,
            )
        except Exception:
            self._logger.exception("unwind_joint6 failed")
            return False
        return result >= 0

    def enable_safety_walls(self) -> bool:
        return bool(self._robot.enable_safety_walls())

    def disable_safety_walls(self) -> bool:
        return bool(self._robot.disable_safety_walls())

    def are_safety_walls_enabled(self):
        return self._robot.are_safety_walls_enabled()

    def get_safety_walls_status(self) -> dict:
        return self._robot.get_safety_walls_status()

    def validate_pose(
        self,
        start_position,
        target_position,
        tool: int = 0,
        user: int = 0,
        start_joint_state: dict | None = None,
    ) -> dict:
        return self._robot.validate_pose(
            start_position,
            target_position,
            tool=tool,
            user=user,
            start_joint_state=start_joint_state,
        )

    def set_digital_output(self, port_id: int, value: bool) -> bool:
        try:
            result = self._robot.set_digital_output(port_id, value)
        except Exception:
            self._logger.exception("set_digital_output failed: port=%s value=%s", port_id, value)
            return False
        return result >= 0

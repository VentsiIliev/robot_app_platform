import logging
import math
from typing import List

from src.engine.robot.enums.axis import RobotAxis, Direction
from src.engine.robot.interfaces.i_robot import IRobot
from src.engine.robot.motion_sequence import MotionSequenceSegment
from src.engine.robot.drivers.client_adapters import build_robot_client

logger = logging.getLogger(__name__)


class Ros2Robot(IRobot):

    def __init__(self, server_url: str):
        logger.info("Ros2Robot init — server_url=%s", server_url)
        self._client = build_robot_client(server_url=server_url)
        logger.info("Ros2Robot ready")

    def move_ptp(self, position: List[float], tool: int, user: int, vel: float, acc: float, blocking: bool = True) -> int:
        logger.debug("move_ptp → pos=%s tool=%s user=%s vel=%s acc=%s", position, tool, user, vel, acc)
        ret = self._client.move_ptp(position, tool, user, vel, acc, blendR=0.0, blocking=blocking)
        ret = ret if isinstance(ret, int) and not isinstance(ret, bool) else -1
        logger.debug("move_ptp ← raw_ret=%s normalised=%s accepted=%s", ret, ret, ret >= 0)
        return ret

    def move_linear(self, position: List[float], tool: int, user: int, vel: float, acc: float, blend_radius: float = 0.0, blocking: bool = True, allow_collision_recovery: bool = False) -> int:
        logger.debug("move_linear → pos=%s tool=%s user=%s vel=%s acc=%s blend=%s", position, tool, user, vel, acc, blend_radius)
        ret = self._client.move_liner(position, tool, user, vel, acc, blend_radius, blocking=blocking,
                                      allow_collision_recovery=allow_collision_recovery)
        ret = ret if isinstance(ret, int) and not isinstance(ret, bool) else -1
        logger.debug("move_linear ← raw_ret=%s accepted=%s", ret, ret >= 0)
        return ret

    def start_jog(self, axis: RobotAxis, direction: Direction, step: float, vel: float, acc: float) -> int:
        logger.debug("start_jog → axis=%s direction=%s step=%s vel=%s acc=%s", axis, direction, step, vel, acc)
        ret = self._client.start_jog(axis, direction, step, vel, acc) or 0
        logger.debug("start_jog ← raw_ret=%s success=%s", ret, ret == 0)
        return ret

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
        logger.debug(
            "start_servo_jog → axis=%s direction=%s linear_mm_s=%s angular_deg_s=%s frame=%s tool=%s user=%s",
            axis,
            direction,
            linear_mm_s,
            angular_deg_s,
            frame,
            tool,
            user,
        )
        starter = getattr(self._client, "start_servo_jog", None)
        if not callable(starter):
            return -1
        ret = starter(
            axis,
            direction,
            linear_mm_s=linear_mm_s,
            angular_deg_s=angular_deg_s,
            frame=frame,
            tool=tool,
            user=user,
        ) or 0
        logger.debug("start_servo_jog ← raw_ret=%s success=%s", ret, ret == 0)
        return ret

    def start_joint_jog(self, joint: str, direction: Direction, step: float, vel: float, acc: float) -> int:
        logger.debug("start_joint_jog → joint=%s direction=%s step=%s vel=%s acc=%s", joint, direction, step, vel, acc)
        starter = getattr(self._client, "start_joint_jog", None)
        if not callable(starter):
            return -1
        ret = starter(joint, direction, step, vel, acc) or 0
        logger.debug("start_joint_jog ← raw_ret=%s success=%s", ret, ret == 0)
        return ret

    def stop_servo_jog(self) -> int:
        logger.debug("stop_servo_jog →")
        stopper = getattr(self._client, "stop_servo_jog", None)
        if not callable(stopper):
            return -1
        ret = stopper()
        ret = ret if isinstance(ret, int) and not isinstance(ret, bool) else -1
        logger.debug("stop_servo_jog ← raw_ret=%s success=%s", ret, ret == 0)
        return ret

    def set_motion_passage_closed(self, passage_id: str, closed: bool) -> bool:
        setter = getattr(self._client, "set_motion_passage_closed", None)
        return bool(callable(setter) and setter(passage_id, closed))

    def stop_motion(self) -> int:
        logger.debug("stop_motion →")
        ret = self._client.stop_motion()
        ret = ret if isinstance(ret, int) and not isinstance(ret, bool) else -1
        logger.debug("stop_motion ← raw_ret=%s success=%s", ret, ret == 0)
        return ret

    def get_state_snapshot(self) -> dict | None:
        snapshot = self._client.get_state_snapshot()
        if not snapshot:
            return None
        snapshot["velocity_magnitude"] = self._vector_magnitude(snapshot.get("velocity"))
        acceleration = snapshot.get("acceleration")
        snapshot["acceleration_magnitude"] = self._vector_magnitude(acceleration)
        if isinstance(acceleration, (list, tuple)):
            snapshot["acceleration_components"] = list(acceleration)
            snapshot["acceleration"] = snapshot["acceleration_magnitude"]
        return snapshot

    @staticmethod
    def _vector_magnitude(values) -> float | None:
        if values is None:
            return None
        try:
            return math.sqrt(sum(float(v) ** 2 for v in values))
        except (TypeError, ValueError):
            return None

    def get_current_position(self) -> List[float]:
        # logger.debug("get_current_position →")
        snapshot = self.get_state_snapshot()
        result = snapshot.get("position") if snapshot else self._client.get_current_position()
        position = result if result is not None else []
        # logger.debug("get_current_position ← raw=%s resolved=%s", result, position)
        return position

    def get_current_position_fresh(self) -> List[float]:
        """Bypass websocket/state caches and query the runtime pose endpoint."""
        result = self._client.get_current_position()
        return result if result is not None else []

    def get_current_flange_position(self) -> List[float] | None:
        return self._client.get_current_flange_position()

    def get_current_base_tcp_position(self) -> List[float] | None:
        getter = getattr(self._client, "get_current_base_tcp_position", None)
        return getter() if callable(getter) else None

    def set_active_tool(self, tool: int) -> bool:
        return self._client.set_active_tool(tool)

    def get_tool_registry(self):
        getter = getattr(self._client, "get_tool_registry", None)
        return getter() if callable(getter) else None

    def set_active_workobject(self, user: int) -> bool:
        setter = getattr(self._client, "set_active_workobject", None)
        if not callable(setter):
            return False
        return bool(setter(user))

    def get_workobject_registry(self):
        getter = getattr(self._client, "get_workobject_registry", None)
        return getter() if callable(getter) else None

    def update_workobject_registry(self, user_id, name=None, transform=None, persist=False):
        updater = getattr(self._client, "update_workobject_registry", None)
        if not callable(updater):
            return -1
        return updater(user_id, name=name, transform=transform, persist=persist)

    def get_current_velocity(self) -> float:
        # logger.debug("get_current_velocity →")
        snapshot = self.get_state_snapshot()
        if snapshot and snapshot.get("velocity_magnitude") is not None:
            return snapshot["velocity_magnitude"]
        result = self._client.get_current_velocity()
        if result is None:
            logger.debug("get_current_velocity ← no data, returning 0.0")
            return 0.0
        _, components = result
        magnitude = math.sqrt(sum(v ** 2 for v in components))
        # logger.debug("get_current_velocity ← components=%s magnitude=%s", components, magnitude)
        return magnitude

    def get_current_acceleration(self) -> float:
        snapshot = self.get_state_snapshot()
        if snapshot and snapshot.get("acceleration_magnitude") is not None:
            return snapshot["acceleration_magnitude"]
        return 0.0

    def get_execution_status(self):
        return self._client.get_status()

    def get_ordered_motion_chain_status(self):
        return self._client.get_ordered_motion_chain_status()

    def get_last_trajectory_command_info(self):
        return self._client.get_last_execute_path_response()

    def unwind_joint6(
        self,
        blocking: bool = True,
        queue_if_busy: bool = True,
        vel: float | None = None,
        acc: float | None = None,
    ) -> int:
        logger.debug(
            "unwind_joint6 → blocking=%s queue_if_busy=%s vel=%s acc=%s",
            blocking,
            queue_if_busy,
            vel,
            acc,
        )
        ret = self._client.unwind_joint6(
            blocking=blocking,
            queue_if_busy=queue_if_busy,
            vel=vel,
            acc=acc,
        )
        ret = ret if isinstance(ret, int) and not isinstance(ret, bool) else -1
        logger.debug("unwind_joint6 ← raw_ret=%s success=%s", ret, ret >= 0)
        return ret

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

    def get_drive_status(self) -> dict:
        return self._client.get_drive_status()

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
        result = self._client.execute_path(
            path,
            rx=rx,
            ry=ry,
            rz=rz,
            vel=vel,
            acc=acc,
            blocking=blocking,
            orientation_mode=orientation_mode,
        )
        logger.debug("execute_trajectory ← result=%s", result)
        return result

    def execute_motion_sequence(
        self,
        segments: List[MotionSequenceSegment],
        tool: int,
        user: int,
        blocking: bool = False,
    ) -> int:
        logger.debug(
            "execute_motion_sequence → segments=%d tool=%s user=%s blocking=%s",
            len(segments),
            tool,
            user,
            blocking,
        )
        result = self._client.execute_sequence(
            segments,
            tool=tool,
            user=user,
            blocking=blocking,
        )
        logger.debug("execute_motion_sequence ← result=%s", result)
        return result

    def execute_custom_motion_sequence(
        self,
        segments: List[MotionSequenceSegment],
        tool: int,
        user: int,
        blocking: bool = False,
    ) -> int:
        logger.debug(
            "execute_custom_motion_sequence → segments=%d tool=%s user=%s blocking=%s",
            len(segments),
            tool,
            user,
            blocking,
        )
        ordered_segments = [
            {
                "type": str(segment.motion_type or "linear"),
                "position": list(segment.position),
                "vel": float(segment.velocity),
                "acc": float(segment.acceleration),
                "blend_radius": float(segment.blend_radius),
            }
            for segment in (segments or [])
        ]
        result = self._client.execute_ordered_motion_chain(
            ordered_segments,
            tool=tool,
            user=user,
            blocking=blocking,
        )
        logger.debug("execute_custom_motion_sequence ← result=%s", result)
        return result

    def execute_ordered_motion_chain(
        self,
        segments: list[dict],
        tool: int,
        user: int,
        blocking: bool = False,
    ) -> int:
        logger.debug(
            "execute_ordered_motion_chain → segments=%d tool=%s user=%s blocking=%s optimizer=Ruckig",
            len(segments) if segments else 0,
            tool,
            user,
            blocking,
        )
        result = self._client.execute_ordered_motion_chain(
            segments=segments,
            tool=tool,
            user=user,
            blocking=blocking,
            trajectory_optimizer="Ruckig",
        )
        logger.debug("execute_ordered_motion_chain ← result=%s", result)
        return result

    def reset_all_errors(self) -> int:
        logger.info("reset_all_errors →")
        ret = self._client.resetAllErrors()
        ret = ret if isinstance(ret, int) and not isinstance(ret, bool) else -1
        logger.info("reset_all_errors ← ret=%s", ret)
        return ret

    def prepare_ordered_motion_chain(self, segments, start_position, tool, user):
        return self._client.prepare_ordered_motion_chain(segments, start_position, tool, user)

    def execute_prepared_ordered_motion_chain(self, plan_id):
        return self._client.execute_prepared_ordered_motion_chain(plan_id)

    def discard_prepared_ordered_motion_chain(self, plan_id):
        return self._client.discard_prepared_ordered_motion_chain(plan_id)

    def get_prepared_ordered_motion_chain(self, plan_id):
        return self._client.get_prepared_ordered_motion_chain(plan_id)

    def set_digital_output(self, port_id: int, value: bool) -> None:
        logger.debug("set_digital_output → port=%s value=%s", port_id, value)
        self._client.setDigitalOutput(port_id, int(value))
        logger.debug("set_digital_output ← done")

    # Unlike the Fairino driver, the ROS2 transport can safely be shared.
    # Reuse this instance so RobotStateManager does not open a second pair
    # of state/execution WebSocket connections.
    def clone(self) -> 'IRobot':
        return self
        # return Ros2Robot(server_url=self._client.server_url)

    def prefers_incremental_jog(self) -> bool:
        return True

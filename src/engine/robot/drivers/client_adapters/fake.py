import logging
from copy import deepcopy

from src.engine.robot.drivers.client_adapters.base import RobotClientAdapter

logger = logging.getLogger(__name__)


class FakeRobotClient(RobotClientAdapter):
    transport_name = "fake"
    _MOTION_ERROR_DRIVE_NOT_ENABLED = -13
    _STOP_STATE_STOPPED = "STOPPED"
    _STOP_STATE_NO_ACTIVE_MOTION = "NO_ACTIVE_MOTION"
    _STOP_STATE_STOP_REQUESTED_BUT_UNCONFIRMED = "STOP_REQUESTED_BUT_UNCONFIRMED"
    _STOP_STATE_ERROR = "ERROR"

    def __init__(self, server_url="fake://robot", ip=None):
        self.server_url = server_url.rstrip("/")
        self.ip = ip or "fake_robot_bridge"
        self._available = True
        self._last_error = None
        self._last_execute_path_response = None
        self._last_stop_response = None
        self._current_position = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self._current_velocity_components = [0.0, 0.0, 0.0]
        self._motion_active = False
        self._queue_size = 0
        self._task_counter = 0
        self._safety_walls_enabled = True
        self._digital_outputs = {}
        self._workobject = None
        self._active_tool = 0
        self._drive_enabled = False
        self._connection_generation = 0
        logger.info("Using fake robot client at %s", self.server_url)

    def _next_task_id(self) -> int:
        self._task_counter += 1
        return self._task_counter

    def _accept_motion(self, position, *, blocking):
        self._current_position = self._to_float_list(position)
        self._current_velocity_components = [0.0, 0.0, 0.0]
        self._motion_active = not bool(blocking)
        self._queue_size = 1 if self._motion_active else 0
        return 0

    def _set_path_result(self, path, *, blocking):
        task_id = self._next_task_id()
        last_position = path[-1] if path else self._current_position
        self._accept_motion(last_position, blocking=blocking)
        self._last_execute_path_response = {
            "http_status": 200,
            "result_code": 0,
            "task_id": task_id,
            "queued": not bool(blocking),
            "queue_position": 0 if blocking else 1,
            "raw": {
                "success": True,
                "result": 0,
                "task_id": task_id,
                "queued": not bool(blocking),
                "queue_position": 0 if blocking else 1,
            },
        }
        return 0

    def health_check(self):
        return {"status": "ok", "message": "Running fake ROS2 client"}

    def get_connection_state(self):
        return "idle" if self._available else "disconnected"

    def get_connection_details(self):
        return {
            "server_url": self.server_url,
            "transport": self.transport_name,
            "state": self.get_connection_state(),
            "last_error": self._last_error,
            "drive_enabled": bool(self._drive_enabled),
            "connection_generation": self._connection_generation,
            "mode": "fake",
        }

    def _motion_preflight_error(self, label: str):
        if not self._drive_enabled:
            logger.warning("%s rejected: fake drive operation is not enabled; call enable() first", label)
            return self._MOTION_ERROR_DRIVE_NOT_ENABLED
        return None

    def move_cartesian(self, position, tool=0, user=0, vel=30, acc=30, blendR=0):
        if not self.set_active_tool(tool):
            return -1
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("FakeRobotClient.move_cartesian")
        if preflight_error is not None:
            return preflight_error
        logger.debug("FakeRobotClient.move_cartesian position=%s", position)
        return self._accept_motion(position, blocking=True)

    def move_liner(self, position, tool=0, user=0, vel=30, acc=30, blendR=0, blocking=True, trajectory_optimizer="TOTG",
                   allow_collision_recovery=False):
        if not self.set_active_tool(tool):
            return -1
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("FakeRobotClient.move_liner")
        if preflight_error is not None:
            return preflight_error
        logger.debug("FakeRobotClient.move_liner position=%s blocking=%s", position, blocking)
        return self._accept_motion(position, blocking=blocking)

    def move_ptp(self, position, tool=0, user=0, vel=30, acc=30, blendR=0, blocking=True, trajectory_optimizer="TOTG"):
        if not self.set_active_tool(tool):
            return -1
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("FakeRobotClient.move_ptp")
        if preflight_error is not None:
            return preflight_error
        logger.debug("FakeRobotClient.move_ptp position=%s blocking=%s", position, blocking)
        return self._accept_motion(position, blocking=blocking)

    def set_active_tool(self, tool: int) -> bool:
        self._active_tool = int(tool)
        return True

    def execute_path(
        self,
        path,
        rx=None,
        ry=None,
        rz=None,
        vel=0.6,
        acc=0.4,
        blocking=False,
        trajectory_optimizer=None,
        orientation_mode="constant",
    ):
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("FakeRobotClient.execute_path")
        if preflight_error is not None:
            return preflight_error
        logger.debug(
            "FakeRobotClient.execute_path waypoints=%s blocking=%s optimizer=%s orientation_mode=%s",
            len(path) if path else 0,
            blocking,
            trajectory_optimizer,
            orientation_mode,
        )
        sanitized_path = [self._to_float_list(p) for p in path] if path else []
        return self._set_path_result(sanitized_path, blocking=blocking)

    def get_last_execute_path_response(self):
        return deepcopy(self._last_execute_path_response)

    def execute_sequence(self, segments, tool=0, user=0, blocking=False):
        if not self.set_active_tool(tool):
            return -1
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("FakeRobotClient.execute_sequence")
        if preflight_error is not None:
            return preflight_error
        logger.debug(
            "FakeRobotClient.execute_sequence segments=%s blocking=%s",
            len(segments) if segments else 0,
            blocking,
        )
        path = [self._to_float_list(segment.position) for segment in segments or []]
        return self._set_path_result(path, blocking=blocking)

    def execute_ordered_motion_chain(self, segments, tool=0, user=0, blocking=False, trajectory_optimizer="TOTG"):
        if not self.set_active_tool(tool):
            return -1
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("FakeRobotClient.execute_ordered_motion_chain")
        if preflight_error is not None:
            return preflight_error
        path = []
        for segment in segments or []:
            segment_type = str(segment.get("type") or segment.get("kind") or "linear").strip().lower()
            if segment_type == "linear" and segment.get("position") is not None:
                path.append(self._to_float_list(segment["position"]))
            elif segment_type == "path":
                path.extend(self._to_float_list(point) for point in segment.get("path") or [])
        return self._set_path_result(path, blocking=blocking)

    def unwind_joint6(self, blocking=True, queue_if_busy=True, vel=None, acc=None):
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("FakeRobotClient.unwind_joint6")
        if preflight_error is not None:
            return preflight_error
        logger.debug("FakeRobotClient.unwind_joint6 blocking=%s queue_if_busy=%s", blocking, queue_if_busy)
        task_id = self._next_task_id()
        self._motion_active = not bool(blocking)
        self._queue_size = 1 if self._motion_active else 0
        self._last_execute_path_response = {
            "http_status": 200,
            "result_code": 0,
            "task_id": task_id,
            "queued": not bool(blocking),
            "queue_position": 0 if blocking else 1,
            "raw": {"success": True, "result": 0, "task_id": task_id, "queued": not bool(blocking)},
        }
        return 0

    def start_jog(self, axis, direction, step, vel, acc):
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("FakeRobotClient.start_jog")
        if preflight_error is not None:
            return preflight_error
        logger.debug(
            "FakeRobotClient.start_jog axis=%s direction=%s step=%s vel=%s acc=%s",
            axis,
            direction,
            step,
            vel,
            acc,
        )
        self._motion_active = True
        self._queue_size = 1
        return 0

    def start_servo_jog(
        self,
        axis,
        direction,
        *,
        linear_mm_s=None,
        angular_deg_s=None,
        frame="user",
        tool=0,
        user=0,
        disable_collision_checking=False,
    ):
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("FakeRobotClient.start_servo_jog")
        if preflight_error is not None:
            return preflight_error
        logger.debug(
            "FakeRobotClient.start_servo_jog axis=%s direction=%s linear_mm_s=%s angular_deg_s=%s frame=%s tool=%s user=%s",
            axis,
            direction,
            linear_mm_s,
            angular_deg_s,
            frame,
            tool,
            user,
        )
        self._motion_active = True
        self._queue_size = 1
        return 0

    def stop_servo_jog(self, *, restore_collision_checking: bool = True):
        logger.debug("FakeRobotClient.stop_servo_jog")
        self._motion_active = False
        self._queue_size = 0
        self._current_velocity_components = [0.0, 0.0, 0.0]
        return 0

    def stop_motion(self):
        logger.debug("FakeRobotClient.stop_motion")
        stop_state = self._STOP_STATE_STOPPED if self._motion_active else self._STOP_STATE_NO_ACTIVE_MOTION
        self._motion_active = False
        self._queue_size = 0
        self._current_velocity_components = [0.0, 0.0, 0.0]
        self._last_stop_response = {
            "success": True,
            "result": 0,
            "stop_state": stop_state,
            "stopped": True,
        }
        return 0

    def get_last_stop_response(self):
        return deepcopy(self._last_stop_response)

    def get_state_snapshot(self):
        return {
            "position": list(self._current_position),
            "velocity": list(self._current_velocity_components),
            "acceleration": [0.0, 0.0, 0.0],
            "source": "fake",
        }

    def get_current_position(self):
        return list(self._current_position)

    def get_current_flange_position(self):
        return list(self._current_position)

    def GetActualTCPPose(self):
        return (0, self.get_current_position())

    def get_status(self):
        return {
            "success": True,
            "mode": "fake",
            "is_executing": self._motion_active,
            "queue_size": self._queue_size,
            "current_position": self.get_current_position(),
        }

    def get_safety_walls_status(self):
        return {
            "supported": True,
            "enabled": self._safety_walls_enabled,
            "success": True,
            "mode": "fake",
        }

    def get_drive_status(self):
        return {
            "success": True,
            "requested_enabled": bool(self._drive_enabled),
            "motion_allowed_by_drive_enable": bool(self._drive_enabled),
            "state": "ENABLE_REQUESTED" if self._drive_enabled else "DISABLED",
            "mode": "fake",
        }

    def validate_pose(
        self,
        start_position,
        target_position,
        tool=0,
        user=0,
        start_joint_state: dict | None = None,
    ) -> dict:
        return {
            "success": True,
            "supported": True,
            "reachable": True,
            "start_position": self._to_float_list(start_position),
            "target_position": self._to_float_list(target_position),
            "mode": "fake",
        }

    def are_safety_walls_enabled(self):
        return self._safety_walls_enabled

    def enable_safety_walls(self) -> bool:
        self._safety_walls_enabled = True
        return True

    def disable_safety_walls(self) -> bool:
        self._safety_walls_enabled = False
        return True

    def get_current_velocity(self):
        return (0, list(self._current_velocity_components))

    def enable(self):
        logger.info("FakeRobotClient.enable")
        self._drive_enabled = True
        return 0

    def RobotEnable(self, state):
        return self.enable() if state == 1 else self.disable()

    def disable(self):
        logger.info("FakeRobotClient.disable")
        self._drive_enabled = False
        return 0

    def setDigitalOutput(self, portId, value):
        self._digital_outputs[int(portId)] = int(value)
        return 0

    def resetAllErrors(self):
        return 0

    def ResetAllError(self):
        return self.resetAllErrors()

    def set_workobject(self, origin, user_id=0):
        self._workobject = {"origin": self._to_float_list(origin), "user_id": int(user_id)}
        return 0

    @staticmethod
    def _to_float_list(position):
        return [float(v) for v in position]

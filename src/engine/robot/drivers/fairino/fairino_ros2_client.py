import logging
import requests

logger = logging.getLogger(__name__)


class FairinoRos2Client:
    _STOP_STATE_STOPPED = "STOPPED"
    _STOP_STATE_NO_ACTIVE_MOTION = "NO_ACTIVE_MOTION"
    _STOP_STATE_STOP_REQUESTED_BUT_UNCONFIRMED = "STOP_REQUESTED_BUT_UNCONFIRMED"
    _STOP_STATE_ERROR = "ERROR"

    def __init__(self, server_url="http://localhost:5000", ip=None):
        self.server_url = server_url.rstrip('/')
        self.ip = ip or "ros2_bridge"
        self._last_execute_path_response = None
        self._last_stop_response = None
        self._available = False
        self._last_error = None
        logger.info("Connecting to ROS2 bridge at %s", self.server_url)
        health = self.health_check()
        logger.debug("health_check response: %s", health)
        if health.get("status") != "ok":
            logger.error("Bridge health check failed: %s", health)
            self._mark_unavailable(health.get("message") or f"Could not connect to ROS2 bridge at {server_url}")
        else:
            self._mark_available()
            logger.info("Connected to ROS2 bridge at %s", server_url)

    def _mark_available(self):
        self._available = True
        self._last_error = None

    def _mark_unavailable(self, message):
        self._available = False
        self._last_error = str(message) if message else "unknown bridge error"

    def get_connection_state(self):
        return "idle" if self._available else "disconnected"

    def get_connection_details(self):
        return {
            "server_url": self.server_url,
            "state": self.get_connection_state(),
            "last_error": self._last_error,
        }

    # AFTER
    @staticmethod
    def _parse_result(raw: dict) -> int:
        value = raw.get("result")
        if isinstance(value, bool):
            return 0 if value else -1
        return value if value is not None else -1

    def health_check(self):
        try:
            response = requests.get(f"{self.server_url}/health", timeout=2)
            data = response.json()
            logger.debug("health_check ← status=%s body=%s", response.status_code, data)
            if data.get("status") == "ok":
                self._mark_available()
            else:
                self._mark_unavailable(data.get("message") or data)
            return data
        except Exception as e:
            logger.warning("health_check error: %s", e)
            self._mark_unavailable(e)
            return {"status": "error", "message": str(e)}

    # ============ Motion Commands ============

    def move_cartesian(self, position, tool=0, user=0, vel=30, acc=30, blendR=0):
        payload = {"position": self._to_float_list(position), "tool": tool, "user": user, "vel": vel, "acc": acc}
        logger.debug("move_cartesian → POST /move/cartesian payload=%s", payload)
        try:
            response = requests.post(f"{self.server_url}/move/cartesian", json=payload, timeout=30)
            raw = response.json()
            self._mark_available()
            result_code = self._parse_result(raw)
            logger.debug(
                "move_cartesian ← http=%s raw=%s result_code=%s",
                response.status_code, raw, result_code,
            )
            return result_code
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("move_cartesian error: %s", e, exc_info=True)
            return -1

    def move_liner(self, position, tool=0, user=0, vel=30, acc=30, blendR=0, blocking=True):
        payload = {
            "position": self._to_float_list(position),
            "tool": tool,
            "user": user,
            "vel": vel,
            "acc": acc,
            "blocking": blocking,
        }
        logger.debug("move_liner → POST /move/linear payload=%s", payload)
        try:
            response = requests.post(f"{self.server_url}/move/linear", json=payload, timeout=30)
            raw = response.json()
            self._mark_available()
            result_code = self._parse_result(raw)
            logger.debug(
                "move_liner ← http=%s raw=%s result_code=%s",
                response.status_code, raw, result_code,
            )
            return result_code
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("move_liner error: %s", e, exc_info=True)
            return -1

    def execute_path(self, path, rx=None, ry=None, rz=None, vel=0.6, acc=0.4, blocking=False):
        sanitized_path = [self._to_float_list(p) for p in path] if path else path
        payload = {"path": sanitized_path, "rx": rx, "ry": ry, "rz": rz, "vel": vel, "acc": acc, "blocking": blocking}
        logger.debug("execute_path → POST /execute/path waypoints=%d blocking=%s vel=%s acc=%s",
                     len(path) if path else 0, blocking, vel, acc)
        try:
            response = requests.post(f"{self.server_url}/execute/path", json=payload, timeout=120)
            raw = response.json()
            self._mark_available()
            result_code = self._parse_result(raw)
            self._last_execute_path_response = {
                "http_status": response.status_code,
                "result_code": result_code,
                "task_id": raw.get("task_id"),
                "queued": bool(raw.get("queued", False)),
                "queue_position": raw.get("queue_position"),
                "raw": raw,
            }
            logger.debug(
                "execute_path ← http=%s raw=%s result_code=%s",
                response.status_code, raw, result_code,
            )
            return result_code
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("execute_path error: %s", e, exc_info=True)
            return -1

    def get_last_execute_path_response(self):
        return self._last_execute_path_response

    def start_jog(self, axis, direction, step, vel, acc):
        axis_val = axis.value if hasattr(axis, 'value') else axis
        dir_val = direction.value if hasattr(direction, 'value') else direction
        payload = {"axis": axis_val, "direction": dir_val, "step": step, "vel": vel, "acc": acc}
        logger.debug("start_jog → POST /jog payload=%s", payload)
        try:
            response = requests.post(f"{self.server_url}/jog", json=payload, timeout=10)
            raw = response.json()
            self._mark_available()
            result_code = self._parse_result(raw)
            logger.debug(
                "start_jog ← http=%s raw=%s result_code=%s",
                response.status_code, raw, result_code,
            )
            return result_code
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("start_jog error: %s", e, exc_info=True)
            return -1


    def stop_motion(self):
        logger.debug("stop_motion → POST /stop")
        try:
            response = requests.post(f"{self.server_url}/stop", timeout=5)
            raw = response.json()
            self._mark_available()
            self._last_stop_response = raw
            stop_state = raw.get("stop_state")
            result_code = self._parse_stop_result(raw)
            logger.debug(
                "stop_motion ← http=%s raw=%s stop_state=%s result_code=%s",
                response.status_code, raw, stop_state, result_code,
            )
            return result_code
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("stop_motion error: %s", e, exc_info=True)
            return -1

    def get_last_stop_response(self):
        return self._last_stop_response

    def _parse_stop_result(self, raw: dict) -> int:
        stop_state = raw.get("stop_state")
        if stop_state in (self._STOP_STATE_STOPPED, self._STOP_STATE_NO_ACTIVE_MOTION):
            return 0
        if stop_state == self._STOP_STATE_STOP_REQUESTED_BUT_UNCONFIRMED:
            return -2
        if stop_state == self._STOP_STATE_ERROR:
            return raw.get("result", -1)
        return 0 if raw.get("success") else -1



    # ============ State Queries ============

    def get_current_position(self):
        # logger.debug("get_current_position → GET /position/current")
        try:
            response = requests.get(f"{self.server_url}/position/current", timeout=2)
            data = response.json()
            self._mark_available()
            position = data.get("position")
            # logger.debug(
            #     "get_current_position ← http=%s raw=%s position=%s",
            #     response.status_code, data, position,
            # )
            if position is None or isinstance(position, int):
                logger.warning("get_current_position: unexpected position value: %s", position)
                return None
            return position
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("get_current_position error: %s", e, exc_info=True)
            return None

    def GetActualTCPPose(self):
        position = self.get_current_position()
        if position is None:
            return (-1, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        return (0, position)

    def get_status(self):
        try:
            response = requests.get(f"{self.server_url}/status", timeout=2)
            data = response.json()
            self._mark_available()
            logger.debug("get_status ← http=%s raw=%s", response.status_code, data)
            return data
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("get_status error: %s", e, exc_info=True)
            return None

    def get_safety_walls_status(self):
        try:
            response = requests.get(f"{self.server_url}/safety/walls/status", timeout=2)
            data = response.json()
            self._mark_available()
            logger.debug("get_safety_walls_status ← http=%s raw=%s", response.status_code, data)
            return data
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("get_safety_walls_status error: %s", e, exc_info=True)
            return {"supported": False, "enabled": None, "error": str(e)}

    def are_safety_walls_enabled(self):
        try:
            response = requests.get(f"{self.server_url}/safety/walls/enabled", timeout=2)
            data = response.json()
            self._mark_available()
            enabled = data.get("enabled")
            logger.debug("are_safety_walls_enabled ← http=%s raw=%s", response.status_code, data)
            return bool(enabled) if enabled is not None else None
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("are_safety_walls_enabled error: %s", e, exc_info=True)
            return None

    def enable_safety_walls(self) -> bool:
        logger.debug("enable_safety_walls → POST /safety/walls/enable")
        try:
            response = requests.post(f"{self.server_url}/safety/walls/enable", timeout=5)
            data = response.json()
            self._mark_available()
            logger.debug("enable_safety_walls ← http=%s raw=%s", response.status_code, data)
            return bool(data.get("success")) and bool(data.get("enabled"))
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("enable_safety_walls error: %s", e, exc_info=True)
            return False

    def disable_safety_walls(self) -> bool:
        logger.debug("disable_safety_walls → POST /safety/walls/disable")
        try:
            response = requests.post(f"{self.server_url}/safety/walls/disable", timeout=5)
            data = response.json()
            self._mark_available()
            logger.debug("disable_safety_walls ← http=%s raw=%s", response.status_code, data)
            return bool(data.get("success")) and data.get("enabled") is False
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("disable_safety_walls error: %s", e, exc_info=True)
            return False

    def get_current_velocity(self):
        # logger.debug("get_current_velocity → GET /velocity/current")
        try:
            response = requests.get(f"{self.server_url}/velocity/current", timeout=2)
            data = response.json()
            self._mark_available()
            velocity = data.get("velocity")
            # logger.debug(
            #     "get_current_velocity ← http=%s raw=%s velocity=%s",
            #     response.status_code, data, velocity,
            # )
            if velocity is None:
                return None
            return (0, velocity)
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("get_current_velocity error: %s", e, exc_info=True)
            return None

    # ============ Configuration & Control ============

    def enable(self):
        logger.info("enable called (ROS2 robot is always enabled)")
        return 0

    def RobotEnable(self, state):
        return self.enable() if state == 1 else self.disable()

    def disable(self):
        logger.info("disable called (use stop_motion for ROS2)")
        return 0


    def setDigitalOutput(self, portId, value):
        logger.warning("setDigitalOutput: port %s -> %s (not implemented in ROS2)", portId, value)
        return -1


    def resetAllErrors(self):
        logger.info("resetAllErrors called (not applicable in ROS2)")
        return 0

    def ResetAllError(self):
        return self.resetAllErrors()

    # ============ WorkObject Support ============

    def set_workobject(self, origin, user_id=0):
        payload = {"origin": origin, "user_id": user_id}
        logger.debug("set_workobject → POST /workobject/set payload=%s", payload)
        try:
            response = requests.post(f"{self.server_url}/workobject/set", json=payload, timeout=5)
            raw = response.json()
            result_code = 0 if raw.get("success") else -1
            logger.debug(
                "set_workobject ← http=%s raw=%s result_code=%s",
                response.status_code, raw, result_code,
            )
            return result_code
        except Exception as e:
            logger.error("set_workobject error: %s", e, exc_info=True)
            return -1

    @staticmethod
    def _to_float_list(position):
        return [float(v) for v in position]

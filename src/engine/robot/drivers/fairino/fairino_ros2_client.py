import asyncio
import json
import logging
import os
import requests
import threading
import time
from copy import deepcopy
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


class FairinoRos2Client:
    _RECONNECT_CHECK_INTERVAL_S = 1.0
    _HEALTH_ERROR_LOG_INTERVAL_S = 10.0
    _STATE_WS_STALE_AFTER_S = 1.0
    _EXECUTION_WS_STALE_AFTER_S = 1.0
    _STATE_HTTP_FALLBACK_INTERVAL_S = 0.5
    _GLOBAL_LAST_HEALTH_ERROR = None
    _GLOBAL_LAST_HEALTH_ERROR_LOGGED_AT = 0.0
    _MOTION_ERROR_DRIVE_NOT_ENABLED = -13
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
        self._connection_state = "disconnected"
        self._last_error = None
        self._startup_status = {}
        self._last_reconnect_check = 0.0
        self._last_health_error = None
        self._last_health_error_logged_at = 0.0
        self._drive_enabled = False
        self._connection_generation = 0
        self._session = requests.Session()
        self._state_ws_url = self._derive_state_ws_url(self.server_url)
        self._execution_ws_url = self._derive_execution_ws_url(self.server_url)
        self._state_ws_lock = threading.Lock()
        self._state_ws_latest = None
        self._state_ws_last_at = 0.0
        self._state_ws_connected = False
        self._state_ws_stop = threading.Event()
        self._state_ws_thread = None
        self._execution_ws_lock = threading.Lock()
        self._execution_ws_latest = None
        self._execution_ws_last_at = 0.0
        self._execution_ws_connected = False
        self._execution_ws_stop = threading.Event()
        self._execution_ws_thread = None
        self._execution_request_lock = threading.Lock()
        self._last_execution_request_label = None
        self._last_execution_request_sent_at = 0.0
        self._last_execution_request_task_id = None
        self._execution_ws_was_executing = False
        self._state_ws_dependency_missing = False
        self._execution_ws_dependency_missing = False
        self._state_http_snapshot = None
        self._state_http_snapshot_at = 0.0
        logger.info("Connecting to ROS2 bridge at %s", self.server_url)
        health = self.health_check()
        logger.debug("health_check response: %s", health)
        if health.get("status") != "ok":
            logger.error("Bridge health check failed: %s", health)
            self._mark_unavailable(health.get("message") or f"Could not connect to ROS2 bridge at {server_url}")
        else:
            self._mark_available()
            logger.info("Connected to ROS2 bridge at %s", server_url)
        self._start_state_websocket()
        self._start_execution_websocket()

    @staticmethod
    def _derive_state_ws_url(server_url: str) -> str:
        explicit = os.environ.get("FAIRINO_ROS2_STATE_WS_URL")
        if explicit:
            return explicit.rstrip("/")

        parsed = urlparse(server_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        hostname = parsed.hostname or "localhost"
        port = 5001
        netloc = f"{hostname}:{port}"
        return urlunparse((scheme, netloc, "/ws/state", "", "", ""))

    @staticmethod
    def _derive_execution_ws_url(server_url: str) -> str:
        explicit = os.environ.get("FAIRINO_ROS2_EXECUTION_WS_URL")
        if explicit:
            return explicit.rstrip("/")

        parsed = urlparse(server_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        hostname = parsed.hostname or "localhost"
        port = 5002
        netloc = f"{hostname}:{port}"
        return urlunparse((scheme, netloc, "/ws/execution", "", "", ""))

    def _mark_available(self):
        self._available = True
        self._connection_state = "idle"
        self._last_error = None
        self._startup_status = {}

    def _mark_unavailable(self, message, state: str = "disconnected", startup_status: dict | None = None):
        was_available = self._available
        self._available = False
        self._connection_state = str(state or "disconnected")
        self._last_error = str(message) if message else "unknown bridge error"
        self._startup_status = dict(startup_status or {})
        self._drive_enabled = False
        if was_available:
            self._connection_generation += 1

    def reconnect(self):
        health = self.health_check()
        return health.get("status") == "ok"

    def _probe_reconnect_if_needed(self):
        if self._available:
            return
        now = time.monotonic()
        if now - self._last_reconnect_check < self._RECONNECT_CHECK_INTERVAL_S:
            return
        self._last_reconnect_check = now
        self.reconnect()

    def get_connection_state(self):
        self._probe_reconnect_if_needed()
        return "idle" if self._available else self._connection_state

    def get_connection_details(self):
        with self._state_ws_lock:
            ws_age = time.monotonic() - self._state_ws_last_at if self._state_ws_last_at else None
        with self._execution_ws_lock:
            execution_ws_age = time.monotonic() - self._execution_ws_last_at if self._execution_ws_last_at else None
        return {
            "server_url": self.server_url,
            "state": self.get_connection_state(),
            "last_error": self._last_error,
            "startup": dict(self._startup_status),
            "drive_enabled": bool(self._drive_enabled),
            "connection_generation": self._connection_generation,
            "state_ws_url": self._state_ws_url,
            "state_ws_connected": bool(self._state_ws_connected),
            "state_ws_age_s": ws_age,
            "state_ws_dependency_missing": bool(self._state_ws_dependency_missing),
            "execution_ws_url": self._execution_ws_url,
            "execution_ws_connected": bool(self._execution_ws_connected),
            "execution_ws_age_s": execution_ws_age,
            "execution_ws_dependency_missing": bool(self._execution_ws_dependency_missing),
        }

    def _start_state_websocket(self):
        if self._state_ws_thread is not None:
            return
        self._state_ws_thread = threading.Thread(
            target=self._run_state_websocket_thread,
            daemon=True,
            name="FairinoRos2StateWebSocket",
        )
        self._state_ws_thread.start()

    def _run_state_websocket_thread(self):
        try:
            asyncio.run(self._state_websocket_loop())
        except Exception:
            logger.debug("State WebSocket thread exited", exc_info=True)

    async def _state_websocket_loop(self):
        try:
            import websockets
        except Exception as exc:
            self._state_ws_dependency_missing = True
            logger.warning(
                "State WebSocket disabled because the 'websockets' package is unavailable: %s",
                exc,
            )
            return

        while not self._state_ws_stop.is_set():
            try:
                async with websockets.connect(
                    self._state_ws_url,
                    open_timeout=1.0,
                    ping_interval=10.0,
                    ping_timeout=3.0,
                    close_timeout=1.0,
                ) as websocket:
                    self._state_ws_connected = True
                    logger.info("Connected to ROS2 state WebSocket at %s", self._state_ws_url)
                    async for message in websocket:
                        self._accept_state_ws_message(message)
                        if self._state_ws_stop.is_set():
                            break
            except Exception as exc:
                self._state_ws_connected = False
                logger.debug("State WebSocket unavailable at %s: %s", self._state_ws_url, exc)
                await asyncio.sleep(1.0)

    def _accept_state_ws_message(self, message):
        try:
            data = json.loads(message)
        except (TypeError, ValueError):
            logger.debug("Ignoring non-JSON state WebSocket frame: %r", message)
            return
        if data.get("type") != "state":
            return
        if data.get("runtime_ready") is False:
            return

        snapshot = {
            "success": data.get("success", True),
            "partial": bool(data.get("partial", False)),
            "unavailable_fields": list(data.get("unavailable_fields") or []),
            "position": data.get("position"),
            "flange_position": data.get("flange_position"),
            "velocity": data.get("velocity"),
            "acceleration": data.get("acceleration"),
            "timestamp": data.get("timestamp"),
            "sequence": data.get("sequence"),
            "source": "websocket",
        }
        with self._state_ws_lock:
            self._state_ws_latest = snapshot
            self._state_ws_last_at = time.monotonic()
        self._mark_available()

    def _get_state_ws_snapshot(self):
        with self._state_ws_lock:
            if self._state_ws_latest is None or not self._state_ws_last_at:
                return None
            if time.monotonic() - self._state_ws_last_at > self._STATE_WS_STALE_AFTER_S:
                return None
            return dict(self._state_ws_latest)

    def _start_execution_websocket(self):
        if self._execution_ws_thread is not None:
            return
        self._execution_ws_thread = threading.Thread(
            target=self._run_execution_websocket_thread,
            daemon=True,
            name="FairinoRos2ExecutionWebSocket",
        )
        self._execution_ws_thread.start()

    def _run_execution_websocket_thread(self):
        try:
            asyncio.run(self._execution_websocket_loop())
        except Exception:
            logger.debug("Execution WebSocket thread exited", exc_info=True)

    async def _execution_websocket_loop(self):
        try:
            import websockets
        except Exception as exc:
            self._execution_ws_dependency_missing = True
            logger.warning(
                "Execution WebSocket disabled because the 'websockets' package is unavailable: %s",
                exc,
            )
            return

        while not self._execution_ws_stop.is_set():
            try:
                async with websockets.connect(
                    self._execution_ws_url,
                    open_timeout=1.0,
                    ping_interval=10.0,
                    ping_timeout=3.0,
                    close_timeout=1.0,
                ) as websocket:
                    self._execution_ws_connected = True
                    logger.info("Connected to ROS2 execution WebSocket at %s", self._execution_ws_url)
                    async for message in websocket:
                        self._accept_execution_ws_message(message)
                        if self._execution_ws_stop.is_set():
                            break
            except Exception as exc:
                self._execution_ws_connected = False
                logger.debug("Execution WebSocket unavailable at %s: %s", self._execution_ws_url, exc)
                await asyncio.sleep(1.0)

    def _accept_execution_ws_message(self, message):
        try:
            data = json.loads(message)
        except (TypeError, ValueError):
            logger.debug("Ignoring non-JSON execution WebSocket frame: %r", message)
            return
        if data.get("type") != "execution_status":
            return
        if data.get("runtime_ready") is False:
            return

        status = data.get("status")
        if not isinstance(status, dict):
            logger.debug("Ignoring execution WebSocket frame without status: %s", data)
            return
        snapshot = dict(status)
        snapshot["success"] = bool(data.get("success", True))
        snapshot["source"] = "websocket"
        snapshot["timestamp"] = data.get("timestamp")
        snapshot["sequence"] = data.get("sequence")
        with self._execution_ws_lock:
            self._execution_ws_latest = snapshot
            self._execution_ws_last_at = time.monotonic()
        self._log_execution_ws_transition(snapshot)
        self._mark_available()

    def _get_execution_ws_status(self):
        with self._execution_ws_lock:
            if self._execution_ws_latest is None or not self._execution_ws_last_at:
                return None
            if time.monotonic() - self._execution_ws_last_at > self._EXECUTION_WS_STALE_AFTER_S:
                return None
            return dict(self._execution_ws_latest)

    def _mark_execution_request_sent(self, label: str) -> float:
        now = time.monotonic()
        with self._execution_request_lock:
            self._last_execution_request_label = str(label)
            self._last_execution_request_sent_at = now
            self._last_execution_request_task_id = None
            self._execution_ws_was_executing = False
        logger.info("[EXECUTION_TIMING] %s request_sent", label)
        return now

    def _mark_execution_request_response(self, label: str, raw: dict, elapsed_s: float) -> None:
        task_id = raw.get("task_id") if isinstance(raw, dict) else None
        with self._execution_request_lock:
            self._last_execution_request_task_id = task_id
        logger.info(
            "[EXECUTION_TIMING] %s response_received elapsed_s=%.3f task_id=%s queued=%s final=%s",
            label,
            elapsed_s,
            task_id,
            raw.get("queued") if isinstance(raw, dict) else None,
            raw.get("final") if isinstance(raw, dict) else None,
        )

    @staticmethod
    def _execution_status_active(status: dict) -> bool:
        if bool(status.get("is_executing")):
            return True
        state = str(status.get("state") or status.get("status") or "").strip().lower()
        if state in {"running", "executing", "active", "moving"}:
            return True
        ordered = status.get("ordered_motion_chain")
        if isinstance(ordered, dict):
            ordered_state = str(ordered.get("state") or ordered.get("status") or "").strip().lower()
            return bool(ordered.get("is_executing")) or ordered_state in {
                "running",
                "executing",
                "active",
                "moving",
            }
        return False

    @staticmethod
    def _execution_status_summary(status: dict) -> dict:
        ordered = status.get("ordered_motion_chain")
        summary = {
            "source": status.get("source"),
            "state": status.get("state") or status.get("status"),
            "is_executing": status.get("is_executing"),
            "task_id": status.get("current_task_id") or status.get("task_id"),
        }
        if isinstance(ordered, dict):
            summary.update({
                "ordered_state": ordered.get("state") or ordered.get("status"),
                "segment_index": ordered.get("current_segment_index"),
                "segment_label": ordered.get("current_segment_label") or ordered.get("segment_label"),
            })
        return {key: value for key, value in summary.items() if value is not None}

    def _log_execution_ws_transition(self, status: dict) -> None:
        active = self._execution_status_active(status)
        now = time.monotonic()
        with self._execution_request_lock:
            was_active = self._execution_ws_was_executing
            self._execution_ws_was_executing = active
            label = self._last_execution_request_label or "execution"
            sent_at = self._last_execution_request_sent_at
            task_id = self._last_execution_request_task_id

        if active and not was_active:
            logger.info(
                "[EXECUTION_TIMING] %s first_active_status after_request_s=%.3f task_id=%s status=%s",
                label,
                now - sent_at if sent_at else -1.0,
                task_id,
                self._execution_status_summary(status),
            )
        elif was_active and not active:
            logger.info(
                "[EXECUTION_TIMING] %s inactive_status after_request_s=%.3f task_id=%s status=%s",
                label,
                now - sent_at if sent_at else -1.0,
                task_id,
                self._execution_status_summary(status),
            )

    @staticmethod
    def _parse_result(raw: dict) -> int:
        value = raw.get("result")
        if isinstance(value, bool):
            return 0 if value else -1
        return value if value is not None else -1

    @staticmethod
    def _error_text(raw: dict, fallback: str) -> str:
        if not isinstance(raw, dict):
            return fallback
        return str(raw.get("error") or raw.get("message") or fallback)

    def _mark_startup_failure_if_present(self, raw: dict, fallback: str) -> bool:
        startup = raw.get("startup") if isinstance(raw, dict) else None
        if not isinstance(startup, dict):
            return False
        state = "error" if startup.get("error") else "starting"
        self._mark_unavailable(
            self._error_text(raw, fallback),
            state=state,
            startup_status=startup,
        )
        return True

    def _response_failed(self, label: str, response, raw: dict) -> bool:
        failed = response.status_code >= 400 or raw.get("success") is False
        if not failed:
            return False
        logger.warning("%s rejected: http=%s raw=%s", label, response.status_code, raw)
        self._mark_startup_failure_if_present(raw, f"{label} failed")
        return True

    def _parse_motion_response(self, label: str, response, raw: dict, *, blocking: bool) -> int:
        result_code = self._parse_result(raw)
        if self._response_failed(label, response, raw):
            return result_code

        queued = bool(raw.get("queued", False))
        final = raw.get("final")
        if blocking and (queued or final is False):
            logger.warning(
                "%s returned non-final response to blocking request: http=%s raw=%s",
                label,
                response.status_code,
                raw,
            )
            return -1

        self._mark_available()
        return result_code

    @staticmethod
    def _execution_info(response, raw: dict, result_code: int) -> dict:
        return {
            "http_status": response.status_code,
            "result_code": result_code,
            "task_id": raw.get("task_id"),
            "queued": bool(raw.get("queued", False)),
            "queue_position": raw.get("queue_position"),
            "accepted": raw.get("accepted"),
            "final": raw.get("final"),
            "state": raw.get("state"),
            "status_url": raw.get("status_url"),
            "status_ws": raw.get("status_ws"),
            "status_ws_port": raw.get("status_ws_port"),
            "raw": raw,
        }

    def health_check(self):
        try:
            response = requests.get(f"{self.server_url}/health", timeout=2)
            data = response.json()
            logger.debug("health_check ← status=%s body=%s", response.status_code, data)
            if data.get("status") == "ok":
                self._mark_available()
                self._last_health_error = None
                self._last_health_error_logged_at = 0.0
            else:
                state = "error" if data.get("error") else "starting"
                self._mark_unavailable(data.get("message") or data, state=state, startup_status=data)
            return data
        except Exception as e:
            self._log_health_check_error(e)
            self._mark_unavailable(e)
            return {"status": "error", "message": str(e)}

    def _log_health_check_error(self, error: Exception) -> None:
        message = str(error)
        now = time.monotonic()
        if (
            message == FairinoRos2Client._GLOBAL_LAST_HEALTH_ERROR
            and (now - FairinoRos2Client._GLOBAL_LAST_HEALTH_ERROR_LOGGED_AT) < self._HEALTH_ERROR_LOG_INTERVAL_S
        ):
            logger.debug("health_check error repeated: %s", message)
            return

        self._last_health_error = message
        self._last_health_error_logged_at = now
        FairinoRos2Client._GLOBAL_LAST_HEALTH_ERROR = message
        FairinoRos2Client._GLOBAL_LAST_HEALTH_ERROR_LOGGED_AT = now
        logger.warning("health_check error: %s", message)

    # ============ Motion Commands ============

    def _motion_preflight_error(self, label: str):
        if not self._available:
            self._probe_reconnect_if_needed()
        if not self._available:
            logger.warning("%s rejected: ROS2 bridge is disconnected", label)
            return -1
        status = self.get_drive_status()
        if status.get("motion_allowed_by_drive_enable") is not None:
            self._drive_enabled = bool(status.get("motion_allowed_by_drive_enable"))
        elif status.get("actual_enabled") is not None:
            self._drive_enabled = bool(status.get("actual_enabled"))
        elif status.get("requested_enabled") is not None:
            self._drive_enabled = bool(status.get("requested_enabled"))
        if not self._drive_enabled:
            logger.info("%s drive is not operation_enabled; requesting enable", label)
            if self.enable() != 0:
                logger.warning("%s rejected: drive operation is not enabled; call enable() first", label)
                return self._MOTION_ERROR_DRIVE_NOT_ENABLED
            for _ in range(10):
                status = self.get_drive_status()
                if status.get("motion_allowed_by_drive_enable") is not None:
                    self._drive_enabled = bool(status.get("motion_allowed_by_drive_enable"))
                elif status.get("actual_enabled") is not None:
                    self._drive_enabled = bool(status.get("actual_enabled"))
                if self._drive_enabled:
                    break
                time.sleep(0.1)
            if not self._drive_enabled:
                logger.warning("%s rejected: drive enable requested but drives are not operation_enabled", label)
                return self._MOTION_ERROR_DRIVE_NOT_ENABLED
        return None

    def move_cartesian(self, position, tool=0, user=0, vel=30, acc=30, blendR=0):
        if not self.set_active_tool(tool):
            return -1
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("move_cartesian")
        if preflight_error is not None:
            return preflight_error
        payload = {"position": self._to_float_list(position), "tool": tool, "user": user, "vel": vel, "acc": acc}
        logger.debug("move_cartesian → POST /move/cartesian payload=%s", payload)
        try:
            request_started = self._mark_execution_request_sent("move_cartesian")
            response = requests.post(f"{self.server_url}/move/cartesian", json=payload, timeout=30)
            raw = response.json()
            result_code = self._parse_motion_response("move_cartesian", response, raw, blocking=True)
            self._mark_execution_request_response("move_cartesian", raw, time.monotonic() - request_started)
            logger.debug(
                "move_cartesian ← http=%s raw=%s result_code=%s",
                response.status_code, raw, result_code,
            )
            return result_code
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("move_cartesian error: %s", e, exc_info=True)
            return -1

    def move_liner(self, position, tool=0, user=0, vel=30, acc=30, blendR=0, blocking=True, trajectory_optimizer="TOTG"):
        if not self.set_active_tool(tool):
            return -1
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("move_liner")
        if preflight_error is not None:
            return preflight_error
        payload = {
            "position": self._to_float_list(position),
            "tool": tool,
            "user": user,
            "vel": vel,
            "acc": acc,
            "blocking": blocking,
            "trajectory_optimizer": trajectory_optimizer,
        }
        logger.debug("move_liner → POST /move/linear payload=%s", payload)
        try:
            request_started = self._mark_execution_request_sent("move_liner")
            response = requests.post(f"{self.server_url}/move/linear", json=payload, timeout=30)
            logger.debug("move_liner ← http=%s response_text=%r", response.status_code,
                         response.text[:500] if response.text else "(empty)")

            raw = response.json()
            result_code = self._parse_motion_response("move_liner", response, raw, blocking=bool(blocking))
            self._mark_execution_request_response("move_liner", raw, time.monotonic() - request_started)
            logger.debug(
                "move_liner ← http=%s raw=%s result_code=%s",
                response.status_code, raw, result_code,
            )
            return result_code
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("move_liner error: %s", e, exc_info=True)
            return -1

    def move_ptp(self, position, tool=0, user=0, vel=30, acc=30, blendR=0, blocking=True, trajectory_optimizer="TOTG"):
        if not self.set_active_tool(tool):
            return -1
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("move_ptp")
        if preflight_error is not None:
            return preflight_error
        payload = {
            "position": self._to_float_list(position),
            "tool": tool,
            "user": user,
            "vel": vel,
            "acc": acc,
            "blocking": blocking,
            "trajectory_optimizer": trajectory_optimizer,
        }
        logger.debug("move_ptp → POST /move/ptp payload=%s", payload)
        try:
            request_started = self._mark_execution_request_sent("move_ptp")
            response = requests.post(f"{self.server_url}/move/ptp", json=payload, timeout=30)
            raw = response.json()
            result_code = self._parse_motion_response("move_ptp", response, raw, blocking=bool(blocking))
            self._mark_execution_request_response("move_ptp", raw, time.monotonic() - request_started)
            logger.debug(
                "move_ptp ← http=%s raw=%s result_code=%s",
                response.status_code, raw, result_code,
            )
            return result_code
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("move_ptp error: %s", e, exc_info=True)
            return -1

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
        preflight_error = self._motion_preflight_error("execute_path")
        if preflight_error is not None:
            return preflight_error
        sanitized_path = [self._to_float_list(p) for p in path] if path else path
        payload = {
            "path": sanitized_path,
            "rx_degrees": rx,
            "ry_degrees": ry,
            "rz_degrees": rz,
            "vel": vel,
            "acc": acc,
            "blocking": blocking,
            "orientation_mode": orientation_mode,
        }
        if trajectory_optimizer:
            payload["trajectory_optimizer"] = trajectory_optimizer
        logger.debug(
            "execute_path → POST /execute/path waypoints=%d blocking=%s vel=%s acc=%s optimizer=%s orientation_mode=%s",
            len(path) if path else 0,
            blocking,
            vel,
            acc,
            trajectory_optimizer,
            orientation_mode,
        )
        try:
            request_started = self._mark_execution_request_sent("execute_path")
            response = requests.post(f"{self.server_url}/execute/path", json=payload, timeout=120)
            raw = response.json()
            result_code = self._parse_motion_response("execute_path", response, raw, blocking=bool(blocking))
            self._last_execute_path_response = self._execution_info(response, raw, result_code)
            self._mark_execution_request_response("execute_path", raw, time.monotonic() - request_started)
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

    def execute_sequence(self, segments, tool=0, user=0, blocking=False):
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("execute_sequence")
        if preflight_error is not None:
            return preflight_error
        payload_segments = []
        for segment in segments or []:
            payload_segments.append(
                {
                    "position": self._to_float_list(segment.position),
                    "vel": float(segment.velocity),
                    "acc": float(segment.acceleration),
                    "motion_type": str(segment.motion_type),
                    "blend_radius": float(segment.blend_radius),
                }
            )
        payload = {
            "segments": payload_segments,
            "tool": int(tool),
            "user": int(user),
            "blocking": bool(blocking),
        }
        logger.debug(
            "execute_sequence → POST /execute/sequence segments=%d blocking=%s",
            len(payload_segments),
            blocking,
        )
        try:
            request_started = self._mark_execution_request_sent("execute_sequence")
            response = requests.post(f"{self.server_url}/execute/sequence", json=payload, timeout=120)
            raw = response.json()
            result_code = self._parse_motion_response("execute_sequence", response, raw, blocking=bool(blocking))
            self._last_execute_path_response = self._execution_info(response, raw, result_code)
            self._mark_execution_request_response("execute_sequence", raw, time.monotonic() - request_started)
            logger.debug(
                "execute_sequence ← http=%s raw=%s result_code=%s",
                response.status_code,
                raw,
                result_code,
            )
            return result_code
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("execute_sequence error: %s", e, exc_info=True)
            return -1

    def execute_ordered_motion_chain(self, segments, tool=0, user=0, blocking=False, trajectory_optimizer="TOTG"):
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("execute_ordered_motion_chain")
        if preflight_error is not None:
            return preflight_error
        payload = {
            "segments": segments or [],
            "tool": int(tool),
            "user": int(user),
            "blocking": bool(blocking),
        }
        if trajectory_optimizer:
            payload["trajectory_optimizer"] = trajectory_optimizer
        logger.debug(
            "execute_ordered_motion_chain → POST /execute/ordered_motion_chain segments=%d blocking=%s",
            len(payload["segments"]),
            blocking,
        )
        try:
            request_started = self._mark_execution_request_sent("execute_ordered_motion_chain")
            response = requests.post(f"{self.server_url}/execute/ordered_motion_chain", json=payload, timeout=300)
            raw = response.json()
            result_code = self._parse_motion_response(
                "execute_ordered_motion_chain",
                response,
                raw,
                blocking=bool(blocking),
            )
            self._last_execute_path_response = self._execution_info(response, raw, result_code)
            self._mark_execution_request_response(
                "execute_ordered_motion_chain",
                raw,
                time.monotonic() - request_started,
            )
            logger.debug(
                "execute_ordered_motion_chain ← http=%s raw=%s result_code=%s",
                response.status_code,
                raw,
                result_code,
            )
            return result_code
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("execute_ordered_motion_chain error: %s", e, exc_info=True)
            return -1

    def unwind_joint6(self, blocking=True, queue_if_busy=True, vel=None, acc=None):
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("unwind_joint6")
        if preflight_error is not None:
            return preflight_error
        payload = {
            "blocking": bool(blocking),
            "queue_if_busy": bool(queue_if_busy),
        }
        if vel is not None:
            payload["vel"] = float(vel)
        if acc is not None:
            payload["acc"] = float(acc)
        logger.debug("unwind_joint6 → POST /unwind/joint6 payload=%s", payload)
        try:
            request_started = self._mark_execution_request_sent("unwind_joint6")
            response = requests.post(f"{self.server_url}/unwind/joint6", json=payload, timeout=60)
            raw = response.json()
            result_code = self._parse_motion_response("unwind_joint6", response, raw, blocking=bool(blocking))
            self._mark_execution_request_response("unwind_joint6", raw, time.monotonic() - request_started)
            logger.debug(
                "unwind_joint6 ← http=%s raw=%s result_code=%s",
                response.status_code, raw, result_code,
            )
            return result_code
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("unwind_joint6 error: %s", e, exc_info=True)
            return -1

    def start_jog(self, axis, direction, step, vel, acc):
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("start_jog")
        if preflight_error is not None:
            return preflight_error
        axis_val = axis.value if hasattr(axis, 'value') else axis
        dir_val = direction.value if hasattr(direction, 'value') else direction
        payload = {"axis": axis_val, "direction": dir_val, "step": step, "vel": vel, "acc": acc}
        logger.debug("start_jog → POST /jog payload=%s", payload)
        try:
            request_started = self._mark_execution_request_sent("start_jog")
            response = requests.post(f"{self.server_url}/jog", json=payload, timeout=10)
            raw = response.json()
            result_code = self._parse_motion_response("start_jog", response, raw, blocking=True)
            self._mark_execution_request_response("start_jog", raw, time.monotonic() - request_started)
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

    def get_state_snapshot(self):
        ws_snapshot = self._get_state_ws_snapshot()
        if ws_snapshot is not None:
            return ws_snapshot

        now = time.monotonic()
        if (
            self._state_http_snapshot is not None
            and now - self._state_http_snapshot_at < self._STATE_HTTP_FALLBACK_INTERVAL_S
        ):
            return dict(self._state_http_snapshot)

        try:
            response = self._session.get(f"{self.server_url}/state/kinematics", timeout=2)
            data = response.json()
            if response.status_code == 206 and data.get("partial") is True:
                logger.debug("get_state_snapshot partial: http=%s data=%s", response.status_code, data)
                self._mark_available()
                data["source"] = "http"
                self._state_http_snapshot = dict(data)
                self._state_http_snapshot_at = now
                return data
            if self._response_failed("get_state_snapshot", response, data):
                logger.warning(
                    "get_state_snapshot rejected: http=%s data=%s",
                    response.status_code,
                    data,
                )
                return None
            self._mark_available()
            data["source"] = "http"
            self._state_http_snapshot = dict(data)
            self._state_http_snapshot_at = now
            return data
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("get_state_snapshot error: %s", e, exc_info=True)
            return None

    def get_current_position(self):
        # logger.debug("get_current_position → GET /position/current")
        try:
            response = requests.get(f"{self.server_url}/position/current", timeout=2)
            data = response.json()
            position = data.get("position")
            # logger.debug(
            #     "get_current_position ← http=%s raw=%s position=%s",
            #     response.status_code, data, position,
            # )
            if self._response_failed("get_current_position", response, data):
                return None
            if position is None or isinstance(position, int):
                logger.warning("get_current_position: unexpected position value: %s", position)
                return None
            self._mark_available()
            return position
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("get_current_position error: %s", e, exc_info=True)
            return None

    def get_current_flange_position(self):
        try:
            response = requests.get(f"{self.server_url}/position/flange", timeout=2)
            data = response.json()
            position = data.get("position")
            if self._response_failed("get_current_flange_position", response, data) or position is None:
                logger.warning("get_current_flange_position rejected: http=%s data=%s", response.status_code, data)
                return None
            self._mark_available()
            return [float(v) for v in position]
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("get_current_flange_position error: %s", e, exc_info=True)
            return None

    def set_active_tool(self, tool: int) -> bool:
        try:
            tool_id = int(tool)
            response = requests.post(
                f"{self.server_url}/tool/active",
                json={"tool_id": tool_id},
                timeout=5,
            )
            data = response.json()
            if response.status_code >= 400 or data.get("success") is False:
                logger.warning("set_active_tool rejected: tool=%s http=%s data=%s", tool, response.status_code, data)
                return False
            self._mark_available()
            logger.info("Active ROS2 tool set to %s (%s)", tool_id, data.get("tool_name"))
            return True
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("set_active_tool error: %s", e, exc_info=True)
            return False

    def GetActualTCPPose(self):
        position = self.get_current_position()
        if position is None:
            return (-1, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        return (0, position)

    def get_status(self):
        ws_status = self._get_execution_ws_status()
        if ws_status is not None:
            return ws_status

        try:
            response = requests.get(f"{self.server_url}/status", timeout=2)
            data = response.json()
            if self._response_failed("get_status", response, data):
                return None
            self._mark_available()
            logger.debug("get_status ← http=%s raw=%s", response.status_code, data)
            return data
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("get_status error: %s", e, exc_info=True)
            return None

    def get_ordered_motion_chain_status(self):
        try:
            response = requests.get(f"{self.server_url}/execute/ordered_motion_chain/status", timeout=2)
            data = response.json()
            if self._response_failed("get_ordered_motion_chain_status", response, data):
                return None
            self._mark_available()
            logger.debug(
                "get_ordered_motion_chain_status ← http=%s raw=%s",
                response.status_code,
                data,
            )
            return data
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("get_ordered_motion_chain_status error: %s", e, exc_info=True)
            return None

    def get_safety_walls_status(self):
        try:
            response = requests.get(f"{self.server_url}/safety/walls/status", timeout=2)
            data = response.json()
            if self._response_failed("get_safety_walls_status", response, data):
                return data
            self._mark_available()
            logger.debug("get_safety_walls_status ← http=%s raw=%s", response.status_code, data)
            return data
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("get_safety_walls_status error: %s", e, exc_info=True)
            return {"supported": False, "enabled": None, "error": str(e)}

    def get_drive_status(self):
        try:
            response = requests.get(f"{self.server_url}/drive/status", timeout=2)
            data = response.json()
            if self._response_failed("get_drive_status", response, data):
                self._drive_enabled = False
                return data
            self._mark_available()
            if data.get("motion_allowed_by_drive_enable") is not None:
                self._drive_enabled = bool(data.get("motion_allowed_by_drive_enable"))
            elif data.get("actual_enabled") is not None:
                self._drive_enabled = bool(data.get("actual_enabled"))
            elif data.get("requested_enabled") is not None:
                self._drive_enabled = bool(data.get("requested_enabled"))
            return data
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("get_drive_status error: %s", e, exc_info=True)
            return {"success": False, "requested_enabled": None, "error": str(e)}

    def validate_pose(
        self,
        start_position,
        target_position,
        tool=0,
        user=0,
        start_joint_state: dict | None = None,
    ) -> dict:
        payload = {
            "start_position": self._to_float_list(start_position),
            "target_position": self._to_float_list(target_position),
            "tool": int(tool),
            "user": int(user),
        }
        if start_joint_state is not None:
            payload["start_joint_state"] = start_joint_state
        logger.debug("validate_pose → POST /reachability/pose payload=%s", payload)
        try:
            response = requests.post(f"{self.server_url}/reachability/pose", json=payload, timeout=15)
            try:
                data = response.json()
            except Exception:
                body = response.text.strip()
                logger.error(
                    "validate_pose non-JSON response: http=%s body=%r",
                    response.status_code,
                    body[:1000],
                )
                raise
            if response.status_code >= 500:
                self._response_failed("validate_pose", response, data)
            else:
                self._mark_available()
            logger.debug("validate_pose ← http=%s raw=%s", response.status_code, data)
            return data
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("validate_pose error: %s", e, exc_info=True)
            return {"success": False, "supported": False, "reachable": False, "error": str(e)}

    def are_safety_walls_enabled(self):
        try:
            response = requests.get(f"{self.server_url}/safety/walls/enabled", timeout=2)
            data = response.json()
            if self._response_failed("are_safety_walls_enabled", response, data):
                return None
            enabled = data.get("enabled")
            self._mark_available()
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
            if self._response_failed("enable_safety_walls", response, data):
                return False
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
            if self._response_failed("disable_safety_walls", response, data):
                return False
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
            velocity = data.get("velocity")
            # logger.debug(
            #     "get_current_velocity ← http=%s raw=%s velocity=%s",
            #     response.status_code, data, velocity,
            # )
            if self._response_failed("get_current_velocity", response, data):
                return None
            if velocity is None:
                return None
            self._mark_available()
            return (0, velocity)
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("get_current_velocity error: %s", e, exc_info=True)
            return None

    # ============ Configuration & Control ============

    def enable(self):
        logger.info("enable → POST /drive/enable")
        try:
            response = requests.post(f"{self.server_url}/drive/enable", timeout=5)
            raw = response.json()
            if self._response_failed("enable", response, raw):
                logger.warning("enable rejected: http=%s raw=%s", response.status_code, raw)
                return -1
            verified = (
                response.status_code == 200
                and raw.get("success") is True
                and raw.get("actual_enabled") is True
                and raw.get("motion_allowed_by_drive_enable") is True
            )
            if not verified:
                logger.warning("enable not verified: http=%s raw=%s", response.status_code, raw)
                self._drive_enabled = False
                return -1
            self._mark_available()
            self._drive_enabled = True
            logger.info("enable ← http=%s raw=%s", response.status_code, raw)
            return 0
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("enable error: %s", e, exc_info=True)
            return -1

    def RobotEnable(self, state):
        return self.enable() if state == 1 else self.disable()

    def disable(self):
        logger.info("disable → POST /drive/disable")
        try:
            response = requests.post(f"{self.server_url}/drive/disable", timeout=5)
            raw = response.json()
            if self._response_failed("disable", response, raw):
                logger.warning("disable rejected: http=%s raw=%s", response.status_code, raw)
                return -1
            verified = (
                response.status_code == 200
                and raw.get("success") is True
                and raw.get("actual_enabled") is False
                and raw.get("requested_enabled") is False
            )
            if not verified:
                logger.warning("disable not verified: http=%s raw=%s", response.status_code, raw)
                return -1
            self._mark_available()
            self._drive_enabled = False
            logger.info("disable ← http=%s raw=%s", response.status_code, raw)
            return 0
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("disable error: %s", e, exc_info=True)
            return -1


    def setDigitalOutput(self, portId, value):
        payload = {"port": int(portId), "value": int(value)}
        logger.debug("setDigitalOutput → POST /io/digital_output payload=%s", payload)
        try:
            response = requests.post(f"{self.server_url}/io/digital_output", json=payload, timeout=5)
            raw = response.json()
            result_code = self._parse_result(raw)
            if not self._response_failed("setDigitalOutput", response, raw):
                self._mark_available()
            logger.debug(
                "setDigitalOutput ← http=%s raw=%s result_code=%s",
                response.status_code,
                raw,
                result_code,
            )
            return result_code
        except Exception as e:
            self._mark_unavailable(e)
            logger.error("setDigitalOutput error: %s", e, exc_info=True)
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
            if not self._response_failed("set_workobject", response, raw):
                self._mark_available()
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


class FakeRos2Client:
    _MOTION_ERROR_DRIVE_NOT_ENABLED = -13
    _STOP_STATE_STOPPED = "STOPPED"
    _STOP_STATE_NO_ACTIVE_MOTION = "NO_ACTIVE_MOTION"
    _STOP_STATE_STOP_REQUESTED_BUT_UNCONFIRMED = "STOP_REQUESTED_BUT_UNCONFIRMED"
    _STOP_STATE_ERROR = "ERROR"

    def __init__(self, server_url="fake://fairino", ip=None):
        self.server_url = server_url.rstrip("/")
        self.ip = ip or "fake_ros2_bridge"
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
        logger.info("Using fake Fairino ROS2 client at %s", self.server_url)

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
        preflight_error = self._motion_preflight_error("FakeRos2Client.move_cartesian")
        if preflight_error is not None:
            return preflight_error
        logger.debug("FakeRos2Client.move_cartesian position=%s", position)
        return self._accept_motion(position, blocking=True)

    def move_liner(self, position, tool=0, user=0, vel=30, acc=30, blendR=0, blocking=True, trajectory_optimizer="TOTG"):
        if not self.set_active_tool(tool):
            return -1
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("FakeRos2Client.move_liner")
        if preflight_error is not None:
            return preflight_error
        logger.debug("FakeRos2Client.move_liner position=%s blocking=%s", position, blocking)
        return self._accept_motion(position, blocking=blocking)

    def move_ptp(self, position, tool=0, user=0, vel=30, acc=30, blendR=0, blocking=True, trajectory_optimizer="TOTG"):
        if not self.set_active_tool(tool):
            return -1
        if not self._drive_enabled and self.enable() != 0:
            return -1
        preflight_error = self._motion_preflight_error("FakeRos2Client.move_ptp")
        if preflight_error is not None:
            return preflight_error
        logger.debug("FakeRos2Client.move_ptp position=%s blocking=%s", position, blocking)
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
        preflight_error = self._motion_preflight_error("FakeRos2Client.execute_path")
        if preflight_error is not None:
            return preflight_error
        logger.debug(
            "FakeRos2Client.execute_path waypoints=%s blocking=%s optimizer=%s orientation_mode=%s",
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
        preflight_error = self._motion_preflight_error("FakeRos2Client.execute_sequence")
        if preflight_error is not None:
            return preflight_error
        logger.debug(
            "FakeRos2Client.execute_sequence segments=%s blocking=%s",
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
        preflight_error = self._motion_preflight_error("FakeRos2Client.execute_ordered_motion_chain")
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
        preflight_error = self._motion_preflight_error("FakeRos2Client.unwind_joint6")
        if preflight_error is not None:
            return preflight_error
        logger.debug("FakeRos2Client.unwind_joint6 blocking=%s queue_if_busy=%s", blocking, queue_if_busy)
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
        preflight_error = self._motion_preflight_error("FakeRos2Client.start_jog")
        if preflight_error is not None:
            return preflight_error
        logger.debug(
            "FakeRos2Client.start_jog axis=%s direction=%s step=%s vel=%s acc=%s",
            axis,
            direction,
            step,
            vel,
            acc,
        )
        self._motion_active = True
        self._queue_size = 1
        return 0

    def stop_motion(self):
        logger.debug("FakeRos2Client.stop_motion")
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
        logger.info("FakeRos2Client.enable")
        self._drive_enabled = True
        return 0

    def RobotEnable(self, state):
        return self.enable() if state == 1 else self.disable()

    def disable(self):
        logger.info("FakeRos2Client.disable")
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


def should_use_fake_ros2_client(server_url: str | None) -> bool:
    normalized = str(server_url or "").strip().lower()
    return normalized in {"fake", "mock", "test", "sim"} or normalized.startswith(
        ("fake://", "mock://", "test://", "sim://")
    )


def build_fairino_ros2_client(server_url="http://localhost:5000", ip=None):
    if should_use_fake_ros2_client(server_url):
        return FakeRos2Client(server_url=server_url, ip=ip)
    return FairinoRos2Client(server_url=server_url, ip=ip)

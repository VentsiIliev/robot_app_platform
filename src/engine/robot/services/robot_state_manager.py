import logging
import threading
import time
from typing import Any, Callable, List, Optional

from ..interfaces.i_robot import IRobot
from ..interfaces.i_robot_state_provider import IRobotStateProvider
from ..interfaces.i_state_publisher import IStatePublisher
from .robot_state_snapshot import RobotStateSnapshot


def _coerce_joint_snapshot(value: Any) -> dict | None:
    if isinstance(value, dict):
        names = list(value.get("names") or [])
        radians = value.get("radians")
        degrees = value.get("degrees")
    else:
        names = []
        radians = None
        degrees = value

    if isinstance(degrees, str) or not isinstance(degrees, (list, tuple)) or len(degrees) < 6:
        return None
    try:
        clean_degrees = [float(v) for v in degrees[:6]]
    except (TypeError, ValueError):
        return None

    clean = {"degrees": clean_degrees}
    if names:
        clean["names"] = [str(name) for name in names[:6]]
    if isinstance(radians, (list, tuple)) and len(radians) >= 6:
        try:
            clean["radians"] = [float(v) for v in radians[:6]]
        except (TypeError, ValueError):
            pass
    return clean


class RobotStateManager(IRobotStateProvider):

    _POLL_INTERVAL_S = 0.02
    _DRIVE_STATUS_POLL_INTERVAL_S = 1.0

    def __init__(
        self,
        robot: IRobot,
        publisher: Optional[IStatePublisher] = None,
        state_topic: str = "robot/state",
        active_tool_getter: Callable[[], int] | None = None,
    ):
        self._robot = robot
        self._publisher = publisher
        self._state_topic = state_topic
        self._active_tool_getter = active_tool_getter
        self._active_tool_synced: int | None = None
        self._logger = logging.getLogger(self.__class__.__name__)

        self._position: List[float] = []
        self._velocity: float = 0.0
        self._acceleration: float = 0.0
        self._state: str = "idle"
        self._readiness_extra: dict = {
            "robot_ready": True,
            "readiness_state": "idle",
            "readiness_note": "Robot service healthy",
        }
        self._snapshot_extra: dict = {}
        self._drive_status: dict = {}
        self._last_drive_status_at = 0.0
        self._connection_was_disconnected = False
        self._last_connection_generation = None

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # IRobotStateProvider
    # ------------------------------------------------------------------

    @property
    def position(self) -> List[float]:
        with self._lock:
            return self._position

    @property
    def velocity(self) -> float:
        with self._lock:
            return self._velocity

    @property
    def acceleration(self) -> float:
        with self._lock:
            return self._acceleration

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def state_topic(self) -> str:
        return self._state_topic

    def start_monitoring(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="RobotStateMonitor")
        self._thread.start()
        self._logger.info("State monitoring started (poll interval=%.1fs)", self._POLL_INTERVAL_S)

    def refresh_once(self) -> None:
        """Synchronously refresh cached robot state once."""
        try:
            self._poll_once()
        except Exception:
            with self._lock:
                self._state = "error"
            self._logger.warning("State refresh failed", exc_info=True)

    def stop_monitoring(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self._logger.info("State monitoring stopped")

    # ------------------------------------------------------------------
    # Extensibility hook — override to add fields to the snapshot
    # ------------------------------------------------------------------

    def _build_snapshot(self) -> RobotStateSnapshot:
        with self._lock:
            extra = {}
            details_getter = getattr(self._robot, "get_connection_details", None)
            if callable(details_getter):
                try:
                    extra = details_getter() or {}
                except Exception:
                    self._logger.debug("Failed to collect robot connection details", exc_info=True)
            extra = dict(extra) if isinstance(extra, dict) else {}
            extra.update(self._readiness_extra)
            extra.update(self._snapshot_extra)
            return RobotStateSnapshot(
                state=self._state,
                position=list(self._position),
                velocity=self._velocity,
                acceleration=self._acceleration,
                extra=extra,
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        while self._running:
            try:
                self._poll_once()

            except Exception:
                with self._lock:
                    self._state = "error"
                self._logger.warning("State poll failed", exc_info=True)

            time.sleep(self._POLL_INTERVAL_S)

    def _poll_once(self) -> None:
        self._sync_connection_generation()
        state_getter = getattr(self._robot, "get_connection_state", None)
        connection_state = self._read_connection_state(state_getter)

        if connection_state in ("disconnected", "starting", "error", "fault"):
            self._publish_unavailable_state(connection_state)
            return

        if not self._sync_configured_tool():
            self._logger.warning("Failed to configure robot tool", exc_info=True)
            with self._lock:
                self._state = "tool_mismatch"
                self._position = []
                self._readiness_extra = {
                    "robot_ready": False,
                    "readiness_state": "tool_mismatch",
                    "readiness_note": "Configured robot tool could not be activated",
                }
            if self._publisher:
                self._publisher.publish(self._build_snapshot())
            return

        if self._connection_was_disconnected:
            drive_status_getter = getattr(self._robot, "get_drive_status", None)
            if callable(drive_status_getter):
                try:
                    drive_status_getter()
                except Exception:
                    self._logger.debug("Failed to refresh robot drive status after reconnect", exc_info=True)
            with self._lock:
                self._connection_was_disconnected = False

        snapshot_getter = getattr(self._robot, "get_state_snapshot", None)
        snapshot = snapshot_getter() if callable(snapshot_getter) else None
        snapshot_extra = {}
        if snapshot:
            pos = snapshot.get("position")
            joints = snapshot.get("joints")
            joints = _coerce_joint_snapshot(joints)
            if joints is not None:
                snapshot_extra["joints"] = joints
            vel = snapshot.get("velocity_magnitude")
            if vel is None:
                velocity_components = snapshot.get("velocity")
                try:
                    vel = sum(float(v) ** 2 for v in velocity_components) ** 0.5
                except (TypeError, ValueError):
                    vel = None
            acc = snapshot.get("acceleration_magnitude")
            if acc is None:
                acceleration_components = snapshot.get("acceleration")
                try:
                    acc = sum(float(v) ** 2 for v in acceleration_components) ** 0.5
                except (TypeError, ValueError):
                    acc = None
        else:
            self._logger.debug("Robot state snapshot unavailable; keeping last known kinematics")
            pos = None
            vel = None
            acc = None

        connection_state = self._read_connection_state(state_getter)
        if connection_state in ("disconnected", "starting", "error", "fault"):
            self._publish_unavailable_state(connection_state)
            return
        self._update_robot_readiness(connection_state)

        with self._lock:
            self._position = pos or self._position
            self._velocity = vel if vel is not None else self._velocity
            self._acceleration = acc if acc is not None else self._acceleration
            self._state = connection_state or "idle"
            self._snapshot_extra = snapshot_extra

        if self._publisher:
            self._publisher.publish(self._build_snapshot())

    @staticmethod
    def _read_connection_state(state_getter) -> str:
        if not callable(state_getter):
            return "idle"
        state = state_getter()
        return state if isinstance(state, str) and state else "idle"

    def _publish_unavailable_state(self, state: str) -> None:
        with self._lock:
            self._state = state
            self._position = []
            self._velocity = 0.0
            self._acceleration = 0.0
            self._active_tool_synced = None
            self._connection_was_disconnected = state == "disconnected"
            self._readiness_extra = self._readiness_for_unavailable_state(state)
            self._snapshot_extra = {}
        if self._publisher:
            self._publisher.publish(self._build_snapshot())

    def _update_robot_readiness(self, connection_state: str) -> None:
        drive_status = self._read_drive_status()
        drive_warning = self._robot_drive_warning(drive_status)
        if drive_warning:
            readiness = {
                "robot_ready": False,
                "readiness_state": "drive_not_ready",
                "readiness_note": drive_warning,
                "drive_status": drive_status,
            }
        else:
            ready = connection_state == "idle"
            readiness = {
                "robot_ready": ready,
                "readiness_state": connection_state or "unknown",
                "readiness_note": "Robot service healthy" if ready else f"Robot state: {connection_state}",
                "drive_status": drive_status,
            }
        with self._lock:
            self._readiness_extra = readiness

    def _read_drive_status(self) -> dict:
        drive_status_getter = getattr(self._robot, "get_drive_status", None)
        if not callable(drive_status_getter):
            return {}

        now = time.monotonic()
        if self._drive_status and now - self._last_drive_status_at < self._DRIVE_STATUS_POLL_INTERVAL_S:
            return dict(self._drive_status)

        try:
            status = drive_status_getter() or {}
        except Exception as exc:
            status = {"success": False, "error": str(exc)}

        status = status if isinstance(status, dict) else {}
        with self._lock:
            self._drive_status = dict(status)
            self._last_drive_status_at = now
        return dict(status)

    @staticmethod
    def _readiness_for_unavailable_state(state: str) -> dict:
        notes = {
            "disconnected": "Robot bridge is disconnected",
            "starting": "Robot runtime is starting",
            "error": "Robot bridge reported an error",
            "fault": "Robot is faulted",
        }
        return {
            "robot_ready": False,
            "readiness_state": state,
            "readiness_note": notes.get(state, f"Robot state: {state}"),
        }

    @staticmethod
    def _robot_drive_warning(drive_status: dict) -> str:
        if not drive_status:
            return ""
        if drive_status.get("success") is False:
            message = str(drive_status.get("error") or "").lower()
            if "sdo" in message or "ethercat" in message:
                return "EtherCAT communication error"
            if "timed out" in message or "timeout" in message:
                return "Drive status request timed out"
            return "Drive status is unavailable"

        motion_allowed = drive_status.get("motion_allowed_by_drive_enable")
        actual_enabled = drive_status.get("actual_enabled")
        requested_enabled = drive_status.get("requested_enabled")
        if motion_allowed is False:
            if requested_enabled is False:
                return "Robot drives are disabled"
            if actual_enabled is False:
                return RobotStateManager._robot_drive_status_note(drive_status)
            return "Robot drives are not motion-ready"
        return ""

    @staticmethod
    def _robot_drive_status_note(drive_status: dict) -> str:
        status_state = drive_status.get("status_state")
        if isinstance(status_state, (list, tuple)) and status_state:
            states = sorted({str(state) for state in status_state if str(state)})
            if states:
                return "Drive state: " + ", ".join(states[:3])
        state = str(drive_status.get("state") or "").strip()
        if state:
            return f"Drive state: {state}"
        return "EtherCAT/drives are not operation enabled"

    def _sync_configured_tool(self) -> bool:
        if self._active_tool_getter is None:
            self._logger.warning("Failed to get configured robot tool (no active tool getter)", exc_info=True)
            return False

        # self._logger.info("Configured robot tool synced: %s", self._active_tool_getter())

        try:
            desired_tool = int(self._active_tool_getter())
        except Exception:
            self._logger.warning("Failed to read configured robot tool", exc_info=True)
            return False

        if self._active_tool_synced == desired_tool:
            return True

        try:
            ok = bool(self._robot.set_active_tool(desired_tool))
        except Exception:
            self._logger.warning("Failed to activate configured robot tool=%s", desired_tool, exc_info=True)
            return False

        if not ok:
            self._logger.warning("Robot rejected configured active tool=%s", desired_tool)
            return False

        self._active_tool_synced = desired_tool
        self._logger.info("Configured active robot tool synced: %s", desired_tool)
        return True

    def _sync_connection_generation(self) -> None:
        details_getter = getattr(self._robot, "get_connection_details", None)
        if not callable(details_getter):
            return
        try:
            details = details_getter() or {}
        except Exception:
            self._logger.debug("Failed to collect robot connection generation", exc_info=True)
            return
        generation = details.get("connection_generation")
        if generation is None:
            return
        with self._lock:
            if self._last_connection_generation is None:
                self._last_connection_generation = generation
                return
            if generation == self._last_connection_generation:
                return
            self._last_connection_generation = generation
            self._active_tool_synced = None
            self._connection_was_disconnected = True
        self._logger.info("Robot connection generation changed; active tool will be re-synced")

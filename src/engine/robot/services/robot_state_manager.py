import logging
import threading
import time
from typing import List, Optional

from ..interfaces.i_robot import IRobot
from ..interfaces.i_robot_state_provider import IRobotStateProvider
from ..interfaces.i_state_publisher import IStatePublisher
from .robot_state_snapshot import RobotStateSnapshot


class RobotStateManager(IRobotStateProvider):

    _POLL_INTERVAL_S = 0.1

    def __init__(self, robot: IRobot, publisher: Optional[IStatePublisher] = None, state_topic: str = "robot/state"):
        self._robot = robot
        self._publisher = publisher
        self._state_topic = state_topic
        self._logger = logging.getLogger(self.__class__.__name__)

        self._position: List[float] = []
        self._velocity: float = 0.0
        self._acceleration: float = 0.0
        self._state: str = "idle"

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
                state_getter = getattr(self._robot, "get_connection_state", None)
                connection_state = state_getter() if callable(state_getter) else "idle"

                if connection_state == "disconnected":
                    with self._lock:
                        self._state = "disconnected"

                    if self._publisher:
                        self._publisher.publish(self._build_snapshot())

                    time.sleep(self._POLL_INTERVAL_S)
                    continue

                pos  = self._robot.get_current_position()
                vel  = self._robot.get_current_velocity()
                acc  = self._robot.get_current_acceleration()

                with self._lock:
                    self._position     = pos or self._position
                    self._velocity     = vel or self._velocity
                    self._acceleration = acc or self._acceleration
                    self._state        = connection_state or "idle"

                if self._publisher:
                    self._publisher.publish(self._build_snapshot())

            except Exception:
                with self._lock:
                    self._state = "error"
                self._logger.warning("State poll failed", exc_info=True)

            time.sleep(self._POLL_INTERVAL_S)

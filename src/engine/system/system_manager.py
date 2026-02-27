from __future__ import annotations
import logging
import threading
from typing import Optional

from src.engine.system.system_state import (
    SystemBusyState, SystemStateEvent, SystemTopics,
)
from src.engine.system.i_system_manager import ISystemManager
from src.engine.core.i_messaging_service import IMessagingService


class SystemManager(ISystemManager):

    def __init__(self, messaging: IMessagingService):
        self._messaging = messaging
        self._lock      = threading.Lock()
        self._active:   Optional[str] = None
        self._logger    = logging.getLogger(self.__class__.__name__)

    @property
    def is_busy(self) -> bool:
        return self._active is not None

    @property
    def active_process_id(self) -> Optional[str]:
        return self._active

    @property
    def state(self) -> SystemBusyState:
        return SystemBusyState.BUSY if self._active else SystemBusyState.IDLE

    def acquire(self, process_id: str) -> bool:
        with self._lock:
            if self._active is None or self._active == process_id:
                self._active = process_id
                self._publish(SystemBusyState.BUSY, process_id)
                self._logger.info("Acquired by '%s'", process_id)
                return True
            self._logger.warning(
                "Rejected '%s' — application busy with '%s'", process_id, self._active
            )
            return False

    def release(self, process_id: str) -> None:
        with self._lock:
            if self._active != process_id:
                return
            self._active = None
            self._publish(SystemBusyState.IDLE, None)
            self._logger.info("Released by '%s'", process_id)

    def _publish(self, state: SystemBusyState, active: Optional[str]) -> None:
        event = SystemStateEvent(state=state, active_process=active)
        self._messaging.publish(SystemTopics.STATE, event)
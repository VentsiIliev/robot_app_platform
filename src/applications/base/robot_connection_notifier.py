from __future__ import annotations

import logging

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.robot.services.robot_state_snapshot import RobotStateSnapshot
from src.shared_contracts.events.notification_events import (
    DismissNotificationEvent,
    NotificationSeverity,
    NotificationTopics,
    UserNotificationEvent,
)
from src.shared_contracts.events.robot_events import RobotTopics


class RobotConnectionNotifier:
    """Converts robot connection-state changes into user-facing notifications."""

    _SOURCE = "robot_connection"
    _DEDUPE_PREFIX = "robot.connection.disconnected"

    def __init__(self, messaging_service: IMessagingService) -> None:
        self._messaging = messaging_service
        self._active = False
        self._was_disconnected = False
        self._active_dedupe_key: str | None = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def start(self) -> None:
        if self._active:
            return
        self._messaging.subscribe(RobotTopics.STATE, self._on_robot_state)
        self._active = True

    def stop(self) -> None:
        if not self._active:
            return
        try:
            self._messaging.unsubscribe(RobotTopics.STATE, self._on_robot_state)
        except Exception:
            self._logger.warning("Failed to unsubscribe robot connection notifier", exc_info=True)
        self._active = False

    def _on_robot_state(self, snapshot: RobotStateSnapshot) -> None:
        state = getattr(snapshot, "state", "")
        if state != "disconnected":
            self._dismiss_active_warning()
            self._was_disconnected = False
            return

        if self._was_disconnected:
            return

        self._was_disconnected = True
        extra = getattr(snapshot, "extra", {}) or {}
        generation = extra.get("connection_generation")
        dedupe_key = self._DEDUPE_PREFIX
        if generation is not None:
            dedupe_key = f"{dedupe_key}:{generation}"
        self._active_dedupe_key = dedupe_key

        self._messaging.publish(
            NotificationTopics.USER,
            UserNotificationEvent(
                source=self._SOURCE,
                severity=NotificationSeverity.WARNING,
                title_key="notification.robot_disconnected.title",
                message_key="notification.robot_disconnected.message",
                fallback_title="Robot Connection Lost",
                fallback_message=(
                    "No connection with the robot. Check that the robot is powered on "
                    "and the connection is available."
                ),
                dedupe_key=dedupe_key,
            ),
        )

    def _dismiss_active_warning(self) -> None:
        if self._active_dedupe_key is None:
            return
        self._messaging.publish(
            NotificationTopics.DISMISS,
            DismissNotificationEvent(dedupe_key=self._active_dedupe_key),
        )
        self._active_dedupe_key = None

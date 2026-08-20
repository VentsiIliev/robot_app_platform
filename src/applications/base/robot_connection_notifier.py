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
    """Converts robot availability changes into user-facing notifications."""

    _SOURCE = "robot_connection"
    _DEDUPE_PREFIX = "robot.connection.disconnected"
    _READINESS_DEDUPE_PREFIX = "robot.readiness.unavailable"
    _READY_STATES = {"idle"}
    _UNAVAILABLE_STATES = {"disconnected", "starting", "error", "fault", "tool_mismatch", "drive_not_ready"}
    _CONFIGURATION_FAILURE_STATES = {"tool_mismatch", "workobject_mismatch"}

    def __init__(self, messaging_service: IMessagingService, *, suppress_until_ready: bool = False) -> None:
        self._messaging = messaging_service
        self._active = False
        self._was_disconnected = False
        self._active_dedupe_key: str | None = None
        self._suppress_until_ready = bool(suppress_until_ready)
        self._has_seen_ready = not self._suppress_until_ready
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
        alert = self._availability_alert(snapshot)
        if alert is None:
            self._has_seen_ready = True
            self._dismiss_active_warning()
            self._was_disconnected = False
            return

        dedupe_key, fallback_title, fallback_message, detail = alert
        readiness_state = str((getattr(snapshot, "extra", {}) or {}).get("readiness_state") or "").strip().lower()
        if not self._has_seen_ready and readiness_state not in self._CONFIGURATION_FAILURE_STATES:
            return
        if self._active_dedupe_key == dedupe_key:
            return

        self._dismiss_active_warning()
        self._was_disconnected = True
        self._active_dedupe_key = dedupe_key

        self._messaging.publish(
            NotificationTopics.USER,
            UserNotificationEvent(
                source=self._SOURCE,
                severity=NotificationSeverity.WARNING,
                title_key=(
                    "notification.robot_disconnected.title"
                    if dedupe_key.startswith(self._DEDUPE_PREFIX)
                    else ""
                ),
                message_key=(
                    "notification.robot_disconnected.message"
                    if dedupe_key.startswith(self._DEDUPE_PREFIX)
                    else ""
                ),
                fallback_title=fallback_title,
                fallback_message=fallback_message,
                detail=detail,
                dedupe_key=dedupe_key,
            ),
        )

    def _availability_alert(self, snapshot: RobotStateSnapshot) -> tuple[str, str, str, str | None] | None:
        state = str(getattr(snapshot, "state", "") or "").strip().lower()
        extra = getattr(snapshot, "extra", {}) or {}
        readiness_state = str(extra.get("readiness_state") or state).strip().lower()
        robot_ready = extra.get("robot_ready")
        if robot_ready is True or readiness_state in self._READY_STATES:
            return None

        generation = extra.get("connection_generation")
        note = str(extra.get("readiness_note") or "").strip()

        if readiness_state == "disconnected":
            dedupe_key = self._generation_dedupe_key(self._DEDUPE_PREFIX, generation)
            return (
                dedupe_key,
                "Robot Connection Lost",
                "No connection with the robot. Check that the robot is powered on and the connection is available.",
                None,
            )

        if robot_ready is False or readiness_state in self._UNAVAILABLE_STATES or state not in self._READY_STATES:
            dedupe_key = self._generation_dedupe_key(self._READINESS_DEDUPE_PREFIX, generation)
            if readiness_state:
                dedupe_key = f"{dedupe_key}:{readiness_state}"
            message = note or f"Robot is not ready. Current state: {readiness_state or state or 'unknown'}."
            return (
                dedupe_key,
                "Robot Not Ready",
                message,
                None,
            )

        return None

    @staticmethod
    def _generation_dedupe_key(prefix: str, generation: object) -> str:
        if generation is None:
            return prefix
        return f"{prefix}:{generation}"

    def _dismiss_active_warning(self) -> None:
        if self._active_dedupe_key is None:
            return
        self._messaging.publish(
            NotificationTopics.DISMISS,
            DismissNotificationEvent(dedupe_key=self._active_dedupe_key),
        )
        self._active_dedupe_key = None

from __future__ import annotations

import logging
from typing import Callable, Mapping

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget

from src.applications.base.styled_message_box import show_critical, show_info, show_warning
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.notification_events import (
    NotificationSeverity,
    NotificationTopics,
    UserNotificationEvent,
)


class _NotificationBridge(QObject):
    notification = pyqtSignal(object)


class NotificationTextResolver:
    def __init__(self, translate: Callable[[str], str] | None = None) -> None:
        self._translate = translate or (lambda key: key)

    def resolve_text(self, key: str, fallback: str, params: Mapping[str, object]) -> str:
        template = ""
        if key:
            translated = self._translate(key)
            if translated and translated != key:
                template = translated
        if not template:
            template = fallback or key
        if not template:
            return ""
        try:
            return template.format(**dict(params))
        except Exception:
            return template


class UserNotificationPresenter:
    def __init__(
        self,
        parent: QWidget,
        messaging_service: IMessagingService,
        translate: Callable[[str], str] | None = None,
    ) -> None:
        self._parent = parent
        self._messaging = messaging_service
        self._resolver = NotificationTextResolver(translate=translate)
        self._bridge = _NotificationBridge()
        self._bridge.notification.connect(self._show_notification)
        self._active = False
        self._last_dedupe_key: str | None = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def start(self) -> None:
        if self._active:
            return
        self._messaging.subscribe(NotificationTopics.USER, self._on_notification)
        self._active = True

    def stop(self) -> None:
        if not self._active:
            return
        try:
            self._messaging.unsubscribe(NotificationTopics.USER, self._on_notification)
        except Exception:
            self._logger.warning("Failed to unsubscribe notification presenter", exc_info=True)
        self._active = False

    def present(self, event: UserNotificationEvent) -> None:
        self._show_notification(event)

    def _on_notification(self, event: UserNotificationEvent) -> None:
        if not self._active:
            return
        self._bridge.notification.emit(event)

    def _show_notification(self, event: UserNotificationEvent) -> None:
        if event.dedupe_key is not None and event.dedupe_key == self._last_dedupe_key:
            return

        title = self._resolver.resolve_text(event.title_key, event.fallback_title, event.params)
        message = self._resolver.resolve_text(event.message_key, event.fallback_message, event.params)
        if event.detail:
            message = f"{message}\n\n{event.detail}" if message else event.detail

        if event.severity == NotificationSeverity.INFO:
            show_info(self._parent, title, message)
        elif event.severity == NotificationSeverity.WARNING:
            show_warning(self._parent, title, message)
        else:
            show_critical(self._parent, title, message)

        self._last_dedupe_key = event.dedupe_key

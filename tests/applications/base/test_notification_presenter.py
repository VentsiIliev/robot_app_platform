import unittest
from unittest.mock import MagicMock, patch

from src.applications.base.notification_presenter import (
    NotificationTextResolver,
    UserNotificationPresenter,
)
from src.shared_contracts.events.notification_events import (
    NotificationSeverity,
    NotificationTopics,
    UserNotificationEvent,
)


class TestNotificationTextResolver(unittest.TestCase):

    def test_uses_fallback_when_translation_missing(self):
        resolver = NotificationTextResolver(translate=lambda key: key)

        text = resolver.resolve_text(
            key="notification.test.message",
            fallback="Fallback message",
            params={},
        )

        self.assertEqual(text, "Fallback message")

    def test_uses_translated_template_and_formats_params(self):
        resolver = NotificationTextResolver(
            translate=lambda key: {
                "notification.test.title": "Localized {name}",
            }.get(key, key)
        )

        text = resolver.resolve_text(
            key="notification.test.title",
            fallback="Fallback {name}",
            params={"name": "Glue"},
        )

        self.assertEqual(text, "Localized Glue")


class TestUserNotificationPresenter(unittest.TestCase):

    def _make_event(self, **overrides):
        payload = {
            "source": "tests",
            "severity": NotificationSeverity.CRITICAL,
            "title_key": "notification.test.title",
            "message_key": "notification.test.message",
            "fallback_title": "Fallback Title",
            "fallback_message": "Fallback Message",
            "params": {},
            "dedupe_key": None,
        }
        payload.update(overrides)
        return UserNotificationEvent(**payload)

    @patch("src.applications.base.notification_presenter.show_critical")
    def test_present_shows_critical_message(self, mock_show_critical):
        presenter = UserNotificationPresenter(
            parent=MagicMock(),
            messaging_service=MagicMock(),
            translate=lambda key: key,
        )

        presenter.present(self._make_event())

        mock_show_critical.assert_called_once_with(
            presenter._parent,
            "Fallback Title",
            "Fallback Message",
        )

    @patch("src.applications.base.notification_presenter.show_warning")
    def test_dedupes_consecutive_notifications_with_same_key(self, mock_show_warning):
        presenter = UserNotificationPresenter(
            parent=MagicMock(),
            messaging_service=MagicMock(),
            translate=lambda key: key,
        )
        event = self._make_event(
            severity=NotificationSeverity.WARNING,
            dedupe_key="same-warning",
        )

        presenter.present(event)
        presenter.present(event)

        mock_show_warning.assert_called_once()

    def test_start_and_stop_manage_broker_subscription(self):
        broker = MagicMock()
        presenter = UserNotificationPresenter(
            parent=MagicMock(),
            messaging_service=broker,
            translate=lambda key: key,
        )

        presenter.start()
        presenter.stop()

        broker.subscribe.assert_called_once_with(NotificationTopics.USER, presenter._on_notification)
        broker.unsubscribe.assert_called_once_with(NotificationTopics.USER, presenter._on_notification)

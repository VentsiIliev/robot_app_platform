import unittest
from unittest.mock import MagicMock, patch

from src.robot_systems.glue.applications.dashboard.controller.glue_dashboard_controller import (
    GlueDashboardController,
)
from src.shared_contracts.events.notification_events import NotificationTopics, NotificationSeverity
from src.shared_contracts.events.process_events import ProcessState


class TestGlueDashboardController(unittest.TestCase):
    def test_on_start_runs_model_start_in_background_helper(self):
        model = MagicMock()
        view = MagicMock()
        broker = MagicMock()
        controller = GlueDashboardController(model, view, broker)
        controller._active = True
        controller._run_blocking = MagicMock()

        controller._on_start()

        controller._run_blocking.assert_called_once_with(model.start)
        model.start.assert_not_called()

    def test_on_start_does_nothing_when_inactive(self):
        model = MagicMock()
        view = MagicMock()
        broker = MagicMock()
        controller = GlueDashboardController(model, view, broker)
        controller._active = False
        controller._run_blocking = MagicMock()

        controller._on_start()

        controller._run_blocking.assert_not_called()

    def test_process_error_publishes_shared_notification_event(self):
        model = MagicMock()
        view = MagicMock()
        broker = MagicMock()
        controller = GlueDashboardController(model, view, broker)
        controller._active = True
        controller._view_ok = MagicMock(return_value=True)

        controller._on_process_state_str(ProcessState.ERROR.value, "glue", "Something failed")

        broker.publish.assert_called_once()
        topic, event = broker.publish.call_args[0]
        self.assertEqual(topic, NotificationTopics.USER)
        self.assertEqual(event.severity, NotificationSeverity.CRITICAL)
        self.assertEqual(event.source, "glue")
        self.assertEqual(event.fallback_message, "Something failed")

    @patch("src.robot_systems.glue.applications.dashboard.controller.glue_dashboard_controller.QCoreApplication.translate")
    def test_translation_helper_falls_back_to_source_text_when_qt_returns_empty(self, mock_translate):
        mock_translate.return_value = ""

        self.assertEqual(GlueDashboardController._t("Clean"), "Clean")


if __name__ == "__main__":
    unittest.main()

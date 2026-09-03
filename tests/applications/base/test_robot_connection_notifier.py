import unittest

from src.applications.base.robot_connection_notifier import RobotConnectionNotifier
from src.engine.robot.services.robot_state_snapshot import RobotStateSnapshot
from src.shared_contracts.events.notification_events import (
    DismissNotificationEvent,
    NotificationSeverity,
    NotificationTopics,
)
from src.shared_contracts.events.robot_events import RobotTopics


class _Broker:
    def __init__(self) -> None:
        self.subscriptions = {}
        self.published = []

    def subscribe(self, topic, callback) -> None:
        self.subscriptions[topic] = callback

    def unsubscribe(self, topic, callback) -> None:
        if self.subscriptions.get(topic) == callback:
            del self.subscriptions[topic]

    def publish(self, topic, message) -> None:
        self.published.append((topic, message))


class TestRobotConnectionNotifier(unittest.TestCase):

    def _snapshot(self, state: str, last_error: str = "connection unavailable", generation: int = 0):
        return RobotStateSnapshot(
            state=state,
            position=[],
            velocity=0.0,
            acceleration=0.0,
            extra={
                "last_error": last_error,
                "connection_generation": generation,
            },
        )

    def test_start_and_stop_manage_robot_state_subscription(self):
        broker = _Broker()
        notifier = RobotConnectionNotifier(broker)

        notifier.start()
        self.assertIn(RobotTopics.STATE, broker.subscriptions)

        notifier.stop()
        self.assertNotIn(RobotTopics.STATE, broker.subscriptions)

    def test_disconnected_state_publishes_user_warning(self):
        broker = _Broker()
        notifier = RobotConnectionNotifier(broker)
        notifier.start()

        broker.subscriptions[RobotTopics.STATE](self._snapshot("disconnected"))

        self.assertEqual(len(broker.published), 1)
        topic, event = broker.published[0]
        self.assertEqual(topic, NotificationTopics.USER)
        self.assertEqual(event.severity, NotificationSeverity.WARNING)
        self.assertEqual(event.fallback_title, "Robot Connection Lost")
        self.assertIn("No connection with the robot", event.fallback_message)
        self.assertIsNone(event.detail)

    def test_repeated_disconnected_state_is_suppressed_until_recovered(self):
        broker = _Broker()
        notifier = RobotConnectionNotifier(broker)
        notifier.start()
        callback = broker.subscriptions[RobotTopics.STATE]

        callback(self._snapshot("disconnected", generation=0))
        callback(self._snapshot("disconnected", generation=0))
        callback(self._snapshot("idle", generation=0))
        callback(self._snapshot("disconnected", generation=1))

        self.assertEqual(len(broker.published), 3)
        self.assertEqual(
            [topic for topic, _ in broker.published],
            [
                NotificationTopics.USER,
                NotificationTopics.DISMISS,
                NotificationTopics.USER,
            ],
        )
        self.assertEqual(broker.published[0][1].dedupe_key, "robot.connection.disconnected:0")
        self.assertIsInstance(broker.published[1][1], DismissNotificationEvent)
        self.assertEqual(broker.published[1][1].dedupe_key, "robot.connection.disconnected:0")
        self.assertEqual(broker.published[2][1].dedupe_key, "robot.connection.disconnected:1")

    def test_drive_not_ready_state_publishes_readiness_warning_until_idle(self):
        broker = _Broker()
        notifier = RobotConnectionNotifier(broker)
        notifier.start()
        callback = broker.subscriptions[RobotTopics.STATE]

        callback(
            self._snapshot("idle").with_extra(
                robot_ready=False,
                readiness_state="drive_not_ready",
                readiness_note="EtherCAT communication error",
            )
        )
        callback(
            self._snapshot("idle").with_extra(
                robot_ready=False,
                readiness_state="drive_not_ready",
                readiness_note="EtherCAT communication error",
            )
        )
        callback(
            self._snapshot("idle").with_extra(
                robot_ready=True,
                readiness_state="idle",
                readiness_note="Robot service healthy",
            )
        )

        self.assertEqual(len(broker.published), 2)
        warning = broker.published[0][1]
        self.assertEqual(broker.published[0][0], NotificationTopics.USER)
        self.assertEqual(warning.fallback_title, "Robot Not Ready")
        self.assertEqual(warning.fallback_message, "EtherCAT communication error")
        self.assertEqual(warning.dedupe_key, "robot.readiness.unavailable:0:drive_not_ready")
        self.assertIsInstance(broker.published[1][1], DismissNotificationEvent)
        self.assertEqual(broker.published[1][1].dedupe_key, "robot.readiness.unavailable:0:drive_not_ready")

    def test_startup_suppression_ignores_initial_not_ready_until_first_ready(self):
        broker = _Broker()
        notifier = RobotConnectionNotifier(broker, suppress_until_ready=True)
        notifier.start()
        callback = broker.subscriptions[RobotTopics.STATE]

        callback(
            self._snapshot("starting").with_extra(
                robot_ready=False,
                readiness_state="starting",
                readiness_note="Robot runtime is starting",
            )
        )
        callback(
            self._snapshot("idle").with_extra(
                robot_ready=True,
                readiness_state="idle",
                readiness_note="Robot service healthy",
            )
        )
        callback(
            self._snapshot("idle").with_extra(
                robot_ready=False,
                readiness_state="drive_not_ready",
                readiness_note="EtherCAT communication error",
            )
        )

        self.assertEqual(len(broker.published), 1)
        self.assertEqual(broker.published[0][1].fallback_title, "Robot Not Ready")

    def test_startup_configuration_failure_is_shown_immediately(self):
        broker = _Broker()
        notifier = RobotConnectionNotifier(broker, suppress_until_ready=True)
        notifier.start()

        callback = broker.subscriptions[RobotTopics.STATE]
        callback(
            self._snapshot("tool_mismatch").with_extra(
                robot_ready=False,
                readiness_state="tool_mismatch",
                readiness_note="Configured robot tool could not be activated (ID 1): "
                               "tool_id 1 maps to unknown tool 'TOOL_1'",
            )
        )

        self.assertEqual(len(broker.published), 1)
        event = broker.published[0][1]
        self.assertIn("unknown tool 'TOOL_1'", event.fallback_message)


if __name__ == "__main__":
    unittest.main()

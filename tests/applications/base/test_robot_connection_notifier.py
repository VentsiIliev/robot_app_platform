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


if __name__ == "__main__":
    unittest.main()

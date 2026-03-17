import time
import unittest
from unittest.mock import MagicMock, patch

from src.engine.robot.services.robot_state_manager import RobotStateManager
from src.engine.robot.services.robot_state_snapshot import RobotStateSnapshot


class TestRobotStateManager(unittest.TestCase):

    def _make(self, publisher=None):
        robot = MagicMock()
        robot.get_current_position.return_value = [1.0, 2.0, 3.0, 0.0, 0.0, 0.0]
        robot.get_current_velocity.return_value = 10.0
        robot.get_current_acceleration.return_value = 5.0
        return RobotStateManager(robot, publisher=publisher), robot

    def test_initial_state(self):
        mgr, _ = self._make()
        self.assertEqual(mgr.state, "idle")
        self.assertEqual(mgr.velocity, 0.0)
        self.assertEqual(mgr.acceleration, 0.0)
        self.assertEqual(mgr.position, [])

    def test_state_topic_default(self):
        mgr, _ = self._make()
        self.assertEqual(mgr.state_topic, "robot/state")

    def test_state_topic_custom(self):
        robot = MagicMock()
        mgr = RobotStateManager(robot, state_topic="custom/topic")
        self.assertEqual(mgr.state_topic, "custom/topic")

    def test_polling_updates_state(self):
        mgr, _ = self._make()
        mgr._POLL_INTERVAL_S = 0.05
        mgr.start_monitoring()
        time.sleep(0.2)
        mgr.stop_monitoring()
        self.assertEqual(mgr.position, [1.0, 2.0, 3.0, 0.0, 0.0, 0.0])
        self.assertEqual(mgr.velocity, 10.0)
        self.assertEqual(mgr.acceleration, 5.0)

    def test_start_monitoring_starts_thread(self):
        mgr, _ = self._make()
        mgr.start_monitoring()
        self.assertTrue(mgr._running)
        self.assertIsNotNone(mgr._thread)
        mgr.stop_monitoring()

    def test_start_monitoring_idempotent(self):
        mgr, _ = self._make()
        mgr.start_monitoring()
        thread1 = mgr._thread
        mgr.start_monitoring()  # second call — no-op
        self.assertIs(mgr._thread, thread1)
        mgr.stop_monitoring()

    def test_stop_monitoring_stops_thread(self):
        mgr, _ = self._make()
        mgr._POLL_INTERVAL_S = 0.05
        mgr.start_monitoring()
        mgr.stop_monitoring()
        self.assertFalse(mgr._running)

    def test_publisher_called_with_snapshot(self):
        publisher = MagicMock()
        mgr, _ = self._make(publisher=publisher)
        mgr._POLL_INTERVAL_S = 0.05
        mgr.start_monitoring()
        time.sleep(0.2)
        mgr.stop_monitoring()
        publisher.publish.assert_called()
        snapshot = publisher.publish.call_args[0][0]
        self.assertIsInstance(snapshot, RobotStateSnapshot)

    def test_no_publisher_does_not_crash(self):
        mgr, _ = self._make(publisher=None)
        mgr._POLL_INTERVAL_S = 0.05
        mgr.start_monitoring()
        time.sleep(0.2)
        mgr.stop_monitoring()  # should not raise

    def test_build_snapshot_returns_current_state(self):
        mgr, _ = self._make()
        mgr._POLL_INTERVAL_S = 0.05
        mgr.start_monitoring()
        time.sleep(0.2)
        mgr.stop_monitoring()
        snap = mgr._build_snapshot()
        self.assertEqual(snap.velocity, 10.0)
        self.assertEqual(snap.acceleration, 5.0)
        self.assertEqual(snap.position, [1.0, 2.0, 3.0, 0.0, 0.0, 0.0])

    def test_disconnected_robot_publishes_disconnected_state(self):
        publisher = MagicMock()
        robot = MagicMock()
        robot.get_connection_state.return_value = "disconnected"
        robot.get_connection_details.return_value = {"state": "disconnected", "last_error": "bridge down"}
        mgr = RobotStateManager(robot, publisher=publisher)
        mgr._POLL_INTERVAL_S = 0.05

        mgr.start_monitoring()
        time.sleep(0.15)
        mgr.stop_monitoring()

        self.assertEqual(mgr.state, "disconnected")
        publisher.publish.assert_called()
        snapshot = publisher.publish.call_args[0][0]
        self.assertEqual(snapshot.state, "disconnected")
        self.assertEqual(snapshot.extra["last_error"], "bridge down")
        robot.get_current_position.assert_not_called()

    def test_poll_exception_does_not_stop_thread(self):
        robot = MagicMock()
        robot.get_current_position.side_effect = RuntimeError("connection lost")
        mgr = RobotStateManager(robot)
        mgr._POLL_INTERVAL_S = 0.05
        mgr.start_monitoring()
        time.sleep(0.2)
        self.assertTrue(mgr._running)
        mgr.stop_monitoring()

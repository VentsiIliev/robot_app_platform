import time
import unittest
from unittest.mock import MagicMock, patch

from src.engine.robot.services.robot_state_manager import RobotStateManager
from src.engine.robot.services.robot_state_snapshot import RobotStateSnapshot


class TestRobotStateManager(unittest.TestCase):

    def _make(self, publisher=None, active_tool_getter=None):
        robot = MagicMock()
        robot.get_state_snapshot.return_value = {
            "position": [1.0, 2.0, 3.0, 0.0, 0.0, 0.0],
            "velocity_magnitude": 10.0,
            "acceleration": 5.0,
        }
        return RobotStateManager(robot, publisher=publisher, active_tool_getter=active_tool_getter), robot

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
        mgr, _ = self._make(active_tool_getter=lambda: 0)
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
        mgr, _ = self._make(active_tool_getter=lambda: 0)
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

    def test_connection_lost_during_poll_publishes_disconnected_state(self):
        publisher = MagicMock()
        robot = MagicMock()
        robot.get_connection_state.side_effect = ["idle", "disconnected"]
        robot.get_connection_details.return_value = {
            "state": "disconnected",
            "last_error": "bridge down",
        }
        robot.get_state_snapshot.return_value = None
        robot.get_current_position.return_value = []
        robot.get_current_velocity.return_value = None
        robot.get_current_acceleration.return_value = None
        robot.set_active_tool.return_value = True
        mgr = RobotStateManager(robot, publisher=publisher, active_tool_getter=lambda: 0)

        mgr.refresh_once()

        self.assertEqual(mgr.state, "disconnected")
        self.assertEqual(mgr.position, [])
        self.assertEqual(mgr.velocity, 0.0)
        publisher.publish.assert_called()
        snapshot = publisher.publish.call_args[0][0]
        self.assertEqual(snapshot.state, "disconnected")

    def test_starting_robot_publishes_starting_without_robot_reads(self):
        publisher = MagicMock()
        robot = MagicMock()
        robot.get_connection_state.return_value = "starting"
        robot.get_connection_details.return_value = {
            "state": "starting",
            "startup": {"phase": "initializing_runtime"},
        }
        mgr = RobotStateManager(robot, publisher=publisher)

        mgr.refresh_once()

        self.assertEqual(mgr.state, "starting")
        robot.set_active_tool.assert_not_called()
        robot.get_state_snapshot.assert_not_called()
        robot.get_current_position.assert_not_called()
        publisher.publish.assert_called()
        snapshot = publisher.publish.call_args[0][0]
        self.assertEqual(snapshot.state, "starting")

    def test_poll_exception_does_not_stop_thread(self):
        robot = MagicMock()
        robot.get_current_position.side_effect = RuntimeError("connection lost")
        mgr = RobotStateManager(robot)
        mgr._POLL_INTERVAL_S = 0.05
        mgr.start_monitoring()
        time.sleep(0.2)
        self.assertTrue(mgr._running)
        mgr.stop_monitoring()

    def test_refresh_syncs_configured_tool_before_reading_position(self):
        robot = MagicMock()
        calls = []
        robot.set_active_tool.side_effect = lambda tool: calls.append(("set_active_tool", tool)) or True
        robot.get_state_snapshot.side_effect = lambda: calls.append(("get_state_snapshot", None)) or {
            "position": [1, 2, 3, 0, 0, 0],
            "velocity_magnitude": 0.0,
            "acceleration": 0.0,
        }
        mgr = RobotStateManager(robot, active_tool_getter=lambda: 1)

        mgr.refresh_once()

        self.assertEqual(calls[:2], [("set_active_tool", 1), ("get_state_snapshot", None)])
        self.assertEqual(mgr.position, [1, 2, 3, 0, 0, 0])

    def test_refresh_does_not_publish_position_when_tool_sync_fails(self):
        publisher = MagicMock()
        robot = MagicMock()
        robot.set_active_tool.return_value = False
        robot.get_current_position.return_value = [1, 2, 3, 0, 0, 0]
        mgr = RobotStateManager(robot, publisher=publisher, active_tool_getter=lambda: 1)

        mgr.refresh_once()

        self.assertEqual(mgr.state, "tool_mismatch")
        self.assertEqual(mgr.position, [])
        robot.get_current_position.assert_not_called()
        publisher.publish.assert_called()
        snapshot = publisher.publish.call_args[0][0]
        self.assertFalse(snapshot.extra["robot_ready"])
        self.assertEqual(snapshot.extra["readiness_state"], "tool_mismatch")

    def test_refresh_publishes_drive_not_ready_when_drive_status_blocks_motion(self):
        publisher = MagicMock()
        robot = MagicMock()
        robot.get_connection_state.return_value = "idle"
        robot.get_connection_details.return_value = {"state": "idle", "connection_generation": 0}
        robot.set_active_tool.return_value = True
        robot.get_state_snapshot.return_value = {
            "position": [1, 2, 3, 0, 0, 0],
            "velocity_magnitude": 0.0,
            "acceleration": 0.0,
        }
        robot.get_drive_status.return_value = {
            "success": False,
            "error": "Failed to upload SDO: Invalid argument",
        }
        mgr = RobotStateManager(robot, publisher=publisher, active_tool_getter=lambda: 1)

        mgr.refresh_once()

        publisher.publish.assert_called()
        snapshot = publisher.publish.call_args[0][0]
        self.assertEqual(snapshot.state, "idle")
        self.assertFalse(snapshot.extra["robot_ready"])
        self.assertEqual(snapshot.extra["readiness_state"], "drive_not_ready")
        self.assertEqual(snapshot.extra["readiness_note"], "EtherCAT communication error")

    def test_refresh_retries_tool_sync_until_success(self):
        robot = MagicMock()
        robot.set_active_tool.side_effect = [False, True]
        robot.get_state_snapshot.return_value = {
            "position": [1, 2, 3, 0, 0, 0],
            "velocity_magnitude": 0.0,
            "acceleration": 0.0,
        }
        mgr = RobotStateManager(robot, active_tool_getter=lambda: 1)

        mgr.refresh_once()
        mgr.refresh_once()

        self.assertEqual(robot.set_active_tool.call_count, 2)
        self.assertEqual(mgr.position, [1, 2, 3, 0, 0, 0])

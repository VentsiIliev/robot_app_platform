import unittest
from unittest.mock import MagicMock, patch

from src.engine.robot.drivers.fairino.fairino_ros2_client import (
    FairinoRos2Client,
    FakeRos2Client,
    build_fairino_ros2_client,
)


class TestFairinoRos2Client(unittest.TestCase):

    @patch("src.engine.robot.drivers.fairino.fairino_ros2_client.requests.get")
    def test_init_sets_disconnected_state_when_bridge_is_unavailable(self, get_mock):
        get_mock.side_effect = ConnectionError("bridge down")

        client = FairinoRos2Client(server_url="http://localhost:5000")

        self.assertEqual(client.get_connection_state(), "disconnected")
        self.assertIn("bridge down", client.get_connection_details()["last_error"])

    @patch("src.engine.robot.drivers.fairino.fairino_ros2_client.requests.get")
    def test_successful_health_check_marks_client_available(self, get_mock):
        response = MagicMock()
        response.json.return_value = {"status": "ok"}
        get_mock.return_value = response

        client = FairinoRos2Client(server_url="http://localhost:5000")

        self.assertEqual(client.get_connection_state(), "idle")
        self.assertIsNone(client.get_connection_details()["last_error"])

    @patch("src.engine.robot.drivers.fairino.fairino_ros2_client.requests.post")
    @patch("src.engine.robot.drivers.fairino.fairino_ros2_client.requests.get")
    def test_stop_motion_treats_no_active_motion_as_benign(self, get_mock, post_mock):
        health = MagicMock()
        health.json.return_value = {"status": "ok"}
        get_mock.return_value = health
        response = MagicMock()
        response.json.return_value = {
            "stop_state": "NO_ACTIVE_MOTION",
            "stopped": False,
            "result": -1,
            "success": True,
        }
        post_mock.return_value = response

        client = FairinoRos2Client(server_url="http://localhost:5000")

        self.assertEqual(client.stop_motion(), 0)
        self.assertEqual(client.get_last_stop_response()["stop_state"], "NO_ACTIVE_MOTION")

    @patch("src.engine.robot.drivers.fairino.fairino_ros2_client.requests.post")
    @patch("src.engine.robot.drivers.fairino.fairino_ros2_client.requests.get")
    def test_stop_motion_returns_unconfirmed_code_when_stop_not_confirmed(self, get_mock, post_mock):
        health = MagicMock()
        health.json.return_value = {"status": "ok"}
        get_mock.return_value = health
        response = MagicMock()
        response.json.return_value = {
            "stop_state": "STOP_REQUESTED_BUT_UNCONFIRMED",
            "stopped": False,
            "result": 1,
            "success": False,
            "error": "robot executing but no cancellable goal handle was available",
        }
        post_mock.return_value = response

        client = FairinoRos2Client(server_url="http://localhost:5000")

        self.assertEqual(client.stop_motion(), -2)
        self.assertEqual(client.get_last_stop_response()["stop_state"], "STOP_REQUESTED_BUT_UNCONFIRMED")

    def test_fake_client_factory_selects_fake_backend(self):
        client = build_fairino_ros2_client(server_url="fake://local")

        self.assertIsInstance(client, FakeRos2Client)
        self.assertEqual(client.get_connection_state(), "idle")

    def test_fake_client_updates_position_and_reports_execution_info(self):
        client = build_fairino_ros2_client(server_url="fake://local")

        self.assertEqual(client.move_liner([1, 2, 3, 4, 5, 6], blocking=True), 0)
        self.assertEqual(client.get_current_position(), [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

        self.assertEqual(client.execute_path([[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]], blocking=False), 0)
        self.assertEqual(client.get_last_execute_path_response()["task_id"], 1)
        self.assertTrue(client.get_status()["is_executing"])

        self.assertEqual(client.stop_motion(), 0)
        self.assertFalse(client.get_status()["is_executing"])

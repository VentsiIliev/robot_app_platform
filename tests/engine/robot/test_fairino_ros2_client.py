import unittest
from unittest.mock import MagicMock, patch

from src.engine.robot.drivers.fairino.fairino_ros2_client import FairinoRos2Client


class TestFairinoRos2Client(unittest.TestCase):

    @patch("src.engine.robot.drivers.fairino.fairino_ros2_client.requests.get")
    def test_init_does_not_raise_when_bridge_is_unavailable(self, get_mock):
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

import unittest
from unittest.mock import MagicMock, patch

from src.engine.robot.drivers.client_adapters import (
    HttpWebSocketRobotClient,
    FakeRobotClient,
    build_robot_client,
)
from src.engine.robot.drivers.ros2_robot import Ros2Robot


class TestRobotClientAdapters(unittest.TestCase):

    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.get")
    def test_init_sets_disconnected_state_when_bridge_is_unavailable(self, get_mock):
        get_mock.side_effect = ConnectionError("bridge down")

        client = HttpWebSocketRobotClient(server_url="http://localhost:5000")

        self.assertEqual(client.get_connection_state(), "disconnected")
        self.assertIn("bridge down", client.get_connection_details()["last_error"])

    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.get")
    def test_successful_health_check_marks_client_available(self, get_mock):
        response = MagicMock()
        response.json.return_value = {"status": "ok"}
        get_mock.return_value = response

        client = HttpWebSocketRobotClient(server_url="http://localhost:5000")

        self.assertEqual(client.get_connection_state(), "idle")
        self.assertIsNone(client.get_connection_details()["last_error"])

    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.post")
    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.get")
    def test_rejected_active_tool_is_available_to_state_reporting(self, get_mock, post_mock):
        health = MagicMock()
        health.status_code = 200
        health.json.return_value = {"status": "ok"}
        get_mock.return_value = health
        response = MagicMock()
        response.status_code = 400
        response.json.return_value = {
            "success": False,
            "error": "tool_id 1 maps to unknown tool 'TOOL_1'",
        }
        post_mock.return_value = response

        client = HttpWebSocketRobotClient(server_url="http://localhost:5000")

        self.assertFalse(client.set_active_tool(1))
        self.assertEqual(
            client.get_connection_details()["last_command_error"],
            "tool_id 1 maps to unknown tool 'TOOL_1'",
        )

    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.get")
    def test_starting_health_check_reports_starting_state(self, get_mock):
        response = MagicMock()
        response.json.return_value = {
            "status": "initializing_runtime",
            "phase": "initializing_runtime",
            "message": "ROS runtime is initializing",
            "ready": False,
            "error": None,
        }
        get_mock.return_value = response

        client = HttpWebSocketRobotClient(server_url="http://localhost:5000")

        self.assertEqual(client.get_connection_state(), "starting")
        details = client.get_connection_details()
        self.assertEqual(details["startup"]["phase"], "initializing_runtime")
        self.assertIn("ROS runtime is initializing", details["last_error"])

    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.post")
    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.get")
    def test_stop_motion_treats_no_active_motion_as_benign(self, get_mock, post_mock):
        health = MagicMock()
        health.status_code = 200
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

        client = HttpWebSocketRobotClient(server_url="http://localhost:5000")

        self.assertEqual(client.stop_motion(), 0)
        self.assertEqual(client.get_last_stop_response()["stop_state"], "NO_ACTIVE_MOTION")

    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.post")
    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.get")
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

        client = HttpWebSocketRobotClient(server_url="http://localhost:5000")

        self.assertEqual(client.stop_motion(), -2)
        self.assertEqual(client.get_last_stop_response()["stop_state"], "STOP_REQUESTED_BUT_UNCONFIRMED")

    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.post")
    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.get")
    def test_move_linear_sets_active_tool_before_motion(self, get_mock, post_mock):
        health = MagicMock()
        health.status_code = 200
        health.json.return_value = {"status": "ok"}
        drive_status = MagicMock()
        drive_status.status_code = 200
        drive_status.json.return_value = {
            "success": True,
            "actual_enabled": True,
            "motion_allowed_by_drive_enable": True,
        }
        get_mock.side_effect = [health, drive_status]
        active_response = MagicMock()
        active_response.status_code = 200
        active_response.json.return_value = {"success": True, "tool_name": "TOOL_1"}
        enable_response = MagicMock()
        enable_response.status_code = 200
        enable_response.json.return_value = {
            "success": True,
            "result": 0,
            "actual_enabled": True,
            "motion_allowed_by_drive_enable": True,
        }
        move_response = MagicMock()
        move_response.status_code = 200
        move_response.text = '{"success": true, "result": 0}'
        move_response.json.return_value = {"success": True, "result": 0}
        post_mock.side_effect = [active_response, enable_response, move_response]

        client = HttpWebSocketRobotClient(server_url="http://localhost:5000")

        self.assertEqual(client.move_liner([1, 2, 3, 4, 5, 6], tool=1), 0)
        self.assertEqual(post_mock.call_args_list[0].args[0], "http://localhost:5000/tool/active")
        self.assertEqual(post_mock.call_args_list[0].kwargs["json"], {"tool_id": 1})
        self.assertEqual(post_mock.call_args_list[1].args[0], "http://localhost:5000/drive/enable")
        self.assertEqual(post_mock.call_args_list[2].args[0], "http://localhost:5000/move/linear")

    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.get")
    def test_current_position_failure_does_not_mark_client_available(self, get_mock):
        health = MagicMock()
        health.status_code = 200
        health.json.return_value = {"status": "ok"}
        unavailable = MagicMock()
        unavailable.status_code = 503
        unavailable.json.return_value = {"success": False, "error": "current position unavailable"}
        get_mock.side_effect = [health, unavailable]

        client = HttpWebSocketRobotClient(server_url="http://localhost:5000")
        client._mark_unavailable("starting", state="starting")

        self.assertIsNone(client.get_current_position())
        self.assertEqual(client._connection_state, "starting")

    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.post")
    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.get")
    def test_blocking_ordered_chain_rejects_non_final_response(self, get_mock, post_mock):
        health = MagicMock()
        health.status_code = 200
        health.json.return_value = {"status": "ok"}
        drive = MagicMock()
        drive.status_code = 200
        drive.json.return_value = {
            "success": True,
            "actual_enabled": True,
            "motion_allowed_by_drive_enable": True,
        }
        get_mock.side_effect = [health, drive]

        response = MagicMock()
        response.status_code = 202
        response.json.return_value = {
            "success": True,
            "accepted": True,
            "final": False,
            "queued": False,
            "result": 0,
            "task_id": 42,
        }
        post_mock.return_value = response

        client = HttpWebSocketRobotClient(server_url="http://localhost:5000")
        client._drive_enabled = True

        result = client.execute_ordered_motion_chain(
            [{"type": "linear", "position": [1, 2, 3, 4, 5, 6]}],
            blocking=True,
        )

        self.assertEqual(result, -1)
        self.assertEqual(client.get_last_execute_path_response()["task_id"], 42)
        self.assertFalse(client.get_last_execute_path_response()["final"])

    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.post")
    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.get")
    def test_prepared_start_mismatch_response_is_preserved(self, get_mock, post_mock):
        health = MagicMock()
        health.status_code = 200
        health.json.return_value = {"status": "ok"}
        get_mock.return_value = health
        response = MagicMock()
        response.status_code = 409
        response.json.return_value = {
            "success": False,
            "error": "prepared chain start mismatch: xyz_error_mm=2.557",
        }
        post_mock.return_value = response

        client = HttpWebSocketRobotClient(server_url="http://localhost:5000")

        result = client.execute_prepared_ordered_motion_chain("plan-1")

        self.assertEqual(result["error"], "prepared chain start mismatch: xyz_error_mm=2.557")

    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.post")
    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.get")
    def test_controlled_stop_sends_optional_duration(self, get_mock, post_mock):
        health = MagicMock()
        health.status_code = 200
        health.json.return_value = {"status": "ok"}
        get_mock.return_value = health
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "stopped": True,
            "future_work_preserved": True,
        }
        post_mock.return_value = response

        client = HttpWebSocketRobotClient(server_url="http://localhost:5000")
        client.controlled_stop(42, stop_duration_s=0.20)

        self.assertEqual(
            post_mock.call_args.kwargs["json"],
            {"expected_task_id": 42, "stop_duration_s": 0.20},
        )

    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.Session.get")
    @patch("src.engine.robot.drivers.client_adapters.http_websocket.requests.get")
    def test_partial_kinematics_snapshot_is_returned(self, get_mock, session_get_mock):
        health = MagicMock()
        health.status_code = 200
        health.json.return_value = {"status": "ok"}
        get_mock.return_value = health

        response = MagicMock()
        response.status_code = 206
        response.json.return_value = {
            "success": False,
            "partial": True,
            "position": [1, 2, 3, 4, 5, 6],
            "unavailable_fields": ["velocity"],
        }
        session_get_mock.return_value = response

        client = HttpWebSocketRobotClient(server_url="http://localhost:5000")

        self.assertEqual(client.get_state_snapshot()["position"], [1, 2, 3, 4, 5, 6])

    def test_fake_client_factory_selects_fake_backend(self):
        client = build_robot_client(server_url="fake://local")

        self.assertIsInstance(client, FakeRobotClient)
        self.assertEqual(client.get_connection_state(), "idle")

    def test_fake_client_updates_position_and_reports_execution_info(self):
        client = build_robot_client(server_url="fake://local")

        self.assertEqual(client.move_liner([1, 2, 3, 4, 5, 6], blocking=True), 0)
        self.assertEqual(client.get_current_position(), [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

        self.assertEqual(client.execute_path([[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]], blocking=False), 0)
        self.assertEqual(client.get_last_execute_path_response()["task_id"], 1)
        self.assertTrue(client.get_status()["is_executing"])

        self.assertEqual(client.stop_motion(), 0)
        self.assertFalse(client.get_status()["is_executing"])

    def test_fake_robot_exposes_state_snapshot_for_platform_polling(self):
        robot = Ros2Robot(server_url="fake://local")

        snapshot = robot.get_state_snapshot()

        self.assertEqual(snapshot["position"], [0.0] * 6)
        self.assertEqual(snapshot["velocity"], [0.0] * 3)
        self.assertEqual(snapshot["velocity_magnitude"], 0.0)
        self.assertEqual(snapshot["acceleration"], 0.0)

    def test_ros2_robot_forwards_scoped_servo_collision_override(self):
        robot = object.__new__(Ros2Robot)
        robot._client = MagicMock()
        robot._client.start_servo_jog.return_value = 0

        result = robot.start_servo_jog(
            "Z",
            "PLUS",
            linear_mm_s=5.0,
            frame="user",
            tool=1,
            user=1,
            disable_collision_checking=True,
        )

        self.assertEqual(0, result)
        robot._client.start_servo_jog.assert_called_once_with(
            "Z",
            "PLUS",
            linear_mm_s=5.0,
            angular_deg_s=None,
            frame="user",
            tool=1,
            user=1,
            disable_collision_checking=True,
        )

    def test_health_check_error_logging_is_throttled_across_client_instances(self):
        HttpWebSocketRobotClient._GLOBAL_LAST_HEALTH_ERROR = None
        HttpWebSocketRobotClient._GLOBAL_LAST_HEALTH_ERROR_LOGGED_AT = 0.0
        first = object.__new__(HttpWebSocketRobotClient)
        second = object.__new__(HttpWebSocketRobotClient)
        first._last_health_error = None
        first._last_health_error_logged_at = 0.0
        second._last_health_error = None
        second._last_health_error_logged_at = 0.0

        with patch("src.engine.robot.drivers.client_adapters.http_websocket.logger") as log:
            first._log_health_check_error(ConnectionError("bridge down"))
            second._log_health_check_error(ConnectionError("bridge down"))

        log.warning.assert_called_once()
        log.debug.assert_called_once()

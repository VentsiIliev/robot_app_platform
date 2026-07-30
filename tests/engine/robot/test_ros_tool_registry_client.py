import unittest
from unittest.mock import patch

from src.engine.robot.calibration.ros_tool_registry_client import RosToolRegistryClient


class _Response:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return dict(self._payload)


class TestRosToolRegistryClient(unittest.TestCase):
    @patch("src.engine.robot.calibration.ros_tool_registry_client.requests.get")
    def test_get_tool_registry_returns_payload(self, get):
        get.return_value = _Response(
            {
                "success": True,
                "tool_registry": {"TOOL_1": [1, 2, 3, 0, 0, 0]},
                "tool_id_map": {"1": "TOOL_1"},
            }
        )
        client = RosToolRegistryClient("http://robot:5000/")

        result = client.get_tool_registry()

        self.assertEqual(result["tool_registry"]["TOOL_1"], [1, 2, 3, 0, 0, 0])
        get.assert_called_once_with("http://robot:5000/tool/registry", timeout=5.0)

    @patch("src.engine.robot.calibration.ros_tool_registry_client.requests.get")
    def test_get_tool_registry_returns_none_on_http_error(self, get):
        get.return_value = _Response({"success": False, "error": "bad"}, status_code=400)
        client = RosToolRegistryClient()

        self.assertIsNone(client.get_tool_registry())

    @patch("src.engine.robot.calibration.ros_tool_registry_client.requests.post")
    def test_update_tool_posts_transform_payload(self, post):
        post.return_value = _Response({"success": True})
        client = RosToolRegistryClient("http://robot:5000", timeout_s=9.0)

        ok, message = client.update_tool(
            2,
            "TOOL_2",
            [1, 2, 3, 4, 5, 6],
            persist=True,
        )

        self.assertTrue(ok)
        self.assertIn("updated", message)
        post.assert_called_once_with(
            "http://robot:5000/tool/registry/2",
            json={
                "name": "TOOL_2",
                "transform": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                "persist": True,
            },
            timeout=9.0,
        )

    @patch("src.engine.robot.calibration.ros_tool_registry_client.requests.post")
    def test_update_tool_returns_server_error_message(self, post):
        post.return_value = _Response({"success": False, "error": "invalid transform"}, status_code=400)
        client = RosToolRegistryClient()

        ok, message = client.update_tool(1, "TOOL_1", [0, 0, 0, 0, 0, 0], persist=False)

        self.assertFalse(ok)
        self.assertEqual(message, "invalid transform")

    @patch("src.engine.robot.calibration.ros_tool_registry_client.requests.post")
    def test_update_tool_returns_network_error(self, post):
        post.side_effect = RuntimeError("offline")
        client = RosToolRegistryClient()

        ok, message = client.update_tool(1, "TOOL_1", [0, 0, 0, 0, 0, 0], persist=False)

        self.assertFalse(ok)
        self.assertIn("offline", message)

    @patch("src.engine.robot.calibration.ros_tool_registry_client.requests.get")
    def test_get_current_flange_position_returns_pose(self, get):
        get.return_value = _Response({"success": True, "position": [1, 2, 3, 4, 5, 6]})
        client = RosToolRegistryClient("http://robot:5000")

        result = client.get_current_flange_position()

        self.assertEqual(result, [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        get.assert_called_once_with("http://robot:5000/position/flange", timeout=5.0)

    @patch("src.engine.robot.calibration.ros_tool_registry_client.requests.get")
    def test_get_current_flange_position_rejects_bad_length(self, get):
        get.return_value = _Response({"success": True, "position": [1, 2, 3]})
        client = RosToolRegistryClient()

        self.assertIsNone(client.get_current_flange_position())


if __name__ == "__main__":
    unittest.main()

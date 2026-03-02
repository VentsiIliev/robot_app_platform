import json
import os
import tempfile
import unittest

from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
from src.engine.repositories.settings_service_factory import build_from_specs
from src.robot_systems.base_robot_system import SettingsSpec
from src.engine.robot.configuration import RobotSettingsSerializer
from src.robot_systems.glue.settings_ids import SettingsID

APP_NAME = GlueRobotSystem.__name__.lower()  # derive from class, not hardcoded


def _make_service(tmp: str, robot_ip: str = "10.0.0.1", robot_tool: int = 1):
    """Helper: write config to tmp dir and build a SettingsService."""
    path = os.path.join(tmp, APP_NAME, "robot", "config.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"ROBOT_IP": robot_ip, "ROBOT_TOOL": robot_tool}, f)

    specs = [SettingsSpec(SettingsID.ROBOT_CONFIG, RobotSettingsSerializer(), "robot/config.json")]
    return build_from_specs(specs, settings_root=tmp, system_class=GlueRobotSystem)


class TestGlueRobotAppSettings(unittest.TestCase):

    def test_loads_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _make_service(tmp, robot_ip="10.0.0.99", robot_tool=5)
            config = service.get(SettingsID.ROBOT_CONFIG)

            self.assertEqual(config.robot_ip, "10.0.0.99")
            self.assertEqual(config.robot_tool, 5)

    def test_default_robot_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _make_service(tmp, robot_tool=0)
            config = service.get(SettingsID.ROBOT_CONFIG)

            self.assertEqual(config.robot_tool, 0)

    def test_reload_returns_fresh_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _make_service(tmp, robot_ip="10.0.0.1")
            first = service.get(SettingsID.ROBOT_CONFIG)
            self.assertEqual(first.robot_ip, "10.0.0.1")

            # Update the file on disk — path must match APP_NAME
            path = os.path.join(tmp, APP_NAME, "robot", "config.json")
            with open(path, "w") as f:
                json.dump({"ROBOT_IP": "10.0.0.2", "ROBOT_TOOL": 1}, f)

            reloaded = service.reload(SettingsID.ROBOT_CONFIG)
            self.assertEqual(reloaded.robot_ip, "10.0.0.2")
            self.assertIsNot(first, reloaded)

    def test_get_returns_same_instance_without_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _make_service(tmp)
            first = service.get(SettingsID.ROBOT_CONFIG)
            second = service.get(SettingsID.ROBOT_CONFIG)

            self.assertIs(first, second)



if __name__ == "__main__":
    unittest.main()

import inspect
import json
import os
import tempfile
import unittest

from src.robot_apps.glue.glue_robot_app import GlueRobotApp

from src.engine.repositories.settings_service_factory import build_from_specs
from src.robot_apps.base_robot_app import SettingsSpec
from src.robot_apps.glue.settings.robot import (
    MovementGroup,
    RobotSettings,
    RobotSettingsSerializer,
    SafetyLimits,
)

APP_NAME = GlueRobotApp.__name__.lower()  # "gluerobotapp" — derived from actual class


def _get_settings_path(app_class, settings_root: str, storage_key: str) -> str:
    """Mirror exactly what build_from_specs does."""
    app_dir = os.path.dirname(inspect.getfile(app_class))
    return os.path.join(app_dir, settings_root, storage_key)


class TestRobotSettingsSerialiser(unittest.TestCase):

    def test_default_values(self):
        s = RobotSettings()
        self.assertEqual(s.robot_tool, 0)
        self.assertEqual(s.robot_user, 0)
        self.assertIsInstance(s.safety_limits, SafetyLimits)
        self.assertEqual(s.movement_groups, {})

    def test_round_trip(self):
        original = RobotSettings(
            robot_ip="10.0.0.1",
            robot_tool=1,
            robot_user=2,
        )
        restored = RobotSettings.from_dict(original.to_dict())
        self.assertEqual(restored.robot_ip,   original.robot_ip)
        self.assertEqual(restored.robot_tool, original.robot_tool)
        self.assertEqual(restored.robot_user, original.robot_user)

    def test_movement_groups_round_trip(self):
        original = RobotSettings()
        original.movement_groups["HOME"] = MovementGroup(
            velocity=30, acceleration=30,
            position="[100.0, 0.0, 300.0, 180.0, 0.0, 0.0]"
        )
        restored = RobotSettings.from_dict(original.to_dict())
        self.assertIn("HOME", restored.movement_groups)
        self.assertEqual(restored.movement_groups["HOME"].velocity, 30)
        self.assertEqual(
            restored.movement_groups["HOME"].parse_position(),
            [100.0, 0.0, 300.0, 180.0, 0.0, 0.0]
        )

    def test_safety_limits_round_trip(self):
        original = RobotSettings()
        original.safety_limits.x_min = -300
        original.safety_limits.z_max = 600
        restored = RobotSettings.from_dict(original.to_dict())
        self.assertEqual(restored.safety_limits.x_min, -300)
        self.assertEqual(restored.safety_limits.z_max, 600)

    def test_from_dict_missing_keys_uses_defaults(self):
        s = RobotSettings.from_dict({})
        self.assertEqual(s.robot_ip, "192.168.58.2")
        self.assertEqual(s.robot_tool, 0)


class TestRobotSettingsSerializer(unittest.TestCase):

    def setUp(self):
        self.serializer = RobotSettingsSerializer()

    def test_settings_type(self):
        self.assertEqual(self.serializer.settings_type, "robot_config")

    def test_get_default_returns_robot_settings(self):
        default = self.serializer.get_default()
        self.assertIsInstance(default, RobotSettings)

    def test_to_dict_from_dict_round_trip(self):
        original = RobotSettings(robot_ip="10.0.0.5", robot_tool=3)
        data = self.serializer.to_dict(original)
        self.assertIsInstance(data, dict)
        self.assertEqual(data["ROBOT_IP"], "10.0.0.5")
        self.assertEqual(data["ROBOT_TOOL"], 3)
        restored = self.serializer.from_dict(data)
        self.assertEqual(restored.robot_ip, "10.0.0.5")
        self.assertEqual(restored.robot_tool, 3)


class TestSettingsServiceIntegration(unittest.TestCase):
    """Full integration: build_from_specs → file on disk → load → typed object."""

    def test_creates_default_file_and_loads_on_first_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = [SettingsSpec("robot_config", RobotSettingsSerializer(), "robot/config.json")]
            service = build_from_specs(specs, settings_root=tmp, app_class=GlueRobotApp)

            config = service.get("robot_config")

            expected_path = os.path.join(tmp, APP_NAME, "robot", "config.json")
            self.assertTrue(os.path.exists(expected_path))

            self.assertIsInstance(config, RobotSettings)
            self.assertEqual(config.robot_ip, "192.168.58.2")

    def test_loads_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, APP_NAME, "robot", "config.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump({"ROBOT_IP": "10.0.0.99", "ROBOT_TOOL": 5}, f)

            specs = [SettingsSpec("robot_config", RobotSettingsSerializer(), "robot/config.json")]
            service = build_from_specs(specs, settings_root=tmp, app_class=GlueRobotApp)
            config = service.get("robot_config")

            self.assertEqual(config.robot_ip, "10.0.0.99")
            self.assertEqual(config.robot_tool, 5)

    def test_get_returns_cached_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = [SettingsSpec("robot_config", RobotSettingsSerializer(), "robot/config.json")]
            service = build_from_specs(specs, settings_root=tmp, app_class=GlueRobotApp)

            first  = service.get("robot_config")
            second = service.get("robot_config")
            self.assertIs(first, second)

    def test_reload_returns_fresh_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, APP_NAME, "robot", "config.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump({"ROBOT_IP": "10.0.0.1", "ROBOT_TOOL": 1}, f)

            specs = [SettingsSpec("robot_config", RobotSettingsSerializer(), "robot/config.json")]
            service = build_from_specs(specs, settings_root=tmp, app_class=GlueRobotApp)
            first = service.get("robot_config")
            self.assertEqual(first.robot_ip, "10.0.0.1")

            with open(path, "w") as f:
                json.dump({"ROBOT_IP": "10.0.0.2", "ROBOT_TOOL": 1}, f)

            reloaded = service.reload("robot_config")
            self.assertEqual(reloaded.robot_ip, "10.0.0.2")
            self.assertIsNot(first, reloaded)

    def test_save_persists_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = [SettingsSpec("robot_config", RobotSettingsSerializer(), "robot/config.json")]
            service = build_from_specs(specs, settings_root=tmp, app_class=GlueRobotApp)

            config = service.get("robot_config")
            config.robot_ip = "192.168.1.50"
            service.save("robot_config", config)

            reloaded = service.reload("robot_config")
            self.assertEqual(reloaded.robot_ip, "192.168.1.50")

    def test_unknown_key_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = [SettingsSpec("robot_config", RobotSettingsSerializer(), "robot/config.json")]
            service = build_from_specs(specs, settings_root=tmp, app_class=GlueRobotApp)

            with self.assertRaises(KeyError):
                service.get("nonexistent")


if __name__ == "__main__":
    unittest.main()

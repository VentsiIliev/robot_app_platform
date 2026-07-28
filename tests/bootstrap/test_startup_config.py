import json
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.bootstrap.startup_config import (
    StartupConfig,
    load_bootstrap_provider,
    load_startup_config,
)
from src.robot_systems.robot_system_bootstrap_provider import (
    RobotSystemBootstrapProvider,
)


class _TestProvider(RobotSystemBootstrapProvider):
    @property
    def system_class(self):
        return object

    def build_robot(self):
        return object()

    def build_login_view(self, robot_system, messaging_service):
        return object()

    def build_authorization_service(self, robot_system):
        return object()


class TestStartupConfig(unittest.TestCase):
    def test_loads_selected_robot_system(self):
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "platform.json"
            config_path.write_text(
                json.dumps(
                    {
                        "robot_system": "paint",
                        "supported_robot_systems": ["glue", "paint", "welding"],
                    }
                ),
                encoding="utf-8",
            )

            config = load_startup_config(config_path)

        self.assertEqual(
            config,
            StartupConfig(
                robot_system="paint",
                supported_robot_systems=("glue", "paint", "welding"),
            ),
        )

    def test_rejects_dotted_module_path(self):
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "platform.json"
            config_path.write_text(
                json.dumps(
                    {
                        "robot_system": "src.robot_systems.paint",
                        "supported_robot_systems": ["paint"],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "lowercase identifier"):
                load_startup_config(config_path)

    def test_loads_provider_factory_by_convention(self):
        module_name = "src.robot_systems.example.bootstrap_provider"
        module = types.ModuleType(module_name)
        module.create_bootstrap_provider = _TestProvider

        with patch.dict(sys.modules, {module_name: module}):
            provider = load_bootstrap_provider(
                StartupConfig(
                    robot_system="example",
                    supported_robot_systems=("example",),
                )
            )

        self.assertIsInstance(provider, _TestProvider)

    def test_reports_missing_robot_system(self):
        with self.assertRaisesRegex(RuntimeError, "is not installed"):
            load_bootstrap_provider(
                StartupConfig(
                    robot_system="system_that_does_not_exist",
                    supported_robot_systems=("system_that_does_not_exist",),
                )
            )

    def test_rejects_selected_system_not_in_supported_list(self):
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "platform.json"
            config_path.write_text(
                json.dumps(
                    {
                        "robot_system": "paint",
                        "supported_robot_systems": ["glue", "welding"],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "is not listed"):
                load_startup_config(config_path)


if __name__ == "__main__":
    unittest.main()

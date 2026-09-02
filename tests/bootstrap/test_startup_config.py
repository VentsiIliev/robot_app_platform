import json
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.bootstrap.startup_config import (
    RosBackendConfig,
    StartupConfig,
    UiStartupConfig,
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

    def test_loads_ros_backend_config(self):
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "platform.json"
            config_path.write_text(
                json.dumps(
                    {
                        "robot_system": "paint",
                        "supported_robot_systems": ["paint"],
                        "ros_backend": {
                            "auto_launch": False,
                            "auto_stop": False,
                            "launch_script": "~/ros2_ws/launch_zeroerr.sh",
                            "stop_script": "~/ros2_ws/stop_zeroerr.sh",
                            "startup_delay_s": 0,
                            "log_file": "/tmp/backend.log",
                            "status_urls": ["http://localhost:5000/health"],
                            "status_timeout_s": 0.5,
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_startup_config(config_path)

        self.assertEqual(
            config.ros_backend,
            RosBackendConfig(
                auto_launch=False,
                auto_stop=False,
                launch_script="~/ros2_ws/launch_zeroerr.sh",
                stop_script="~/ros2_ws/stop_zeroerr.sh",
                startup_delay_s=0.0,
                log_file="/tmp/backend.log",
                status_urls=("http://localhost:5000/health",),
                status_timeout_s=0.5,
            ),
        )

    def test_loads_ui_startup_config(self):
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "platform.json"
            config_path.write_text(
                json.dumps(
                    {
                        "robot_system": "paint",
                        "supported_robot_systems": ["paint"],
                        "ui": {
                            "dev_skip_login": True,
                            "skip_splash": True,
                            "show_account_button_when_dev_skip_login": True,
                            "show_power_off_button": True,
                            "fullscreen": False,
                            "window_width": 1024,
                            "window_height": 768,
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_startup_config(config_path)

        self.assertEqual(
            config.ui,
            UiStartupConfig(
                dev_skip_login=True,
                skip_splash=True,
                show_account_button_when_dev_skip_login=True,
                show_power_off_button=True,
                fullscreen=False,
                window_width=1024,
                window_height=768,
            ),
        )

    def test_rejects_invalid_ui_window_size(self):
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "platform.json"
            config_path.write_text(
                json.dumps(
                    {
                        "robot_system": "paint",
                        "supported_robot_systems": ["paint"],
                        "ui": {"window_width": 0},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "ui.window_width"):
                load_startup_config(config_path)

    def test_rejects_invalid_ui_bool(self):
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "platform.json"
            config_path.write_text(
                json.dumps(
                    {
                        "robot_system": "paint",
                        "supported_robot_systems": ["paint"],
                        "ui": {"dev_skip_login": "false"},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "ui.dev_skip_login"):
                load_startup_config(config_path)

    def test_rejects_invalid_ros_backend_bool(self):
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "platform.json"
            config_path.write_text(
                json.dumps(
                    {
                        "robot_system": "paint",
                        "supported_robot_systems": ["paint"],
                        "ros_backend": {"auto_launch": "false"},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "ros_backend.auto_launch"):
                load_startup_config(config_path)

    def test_rejects_invalid_ros_backend_path(self):
        with TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "platform.json"
            config_path.write_text(
                json.dumps(
                    {
                        "robot_system": "paint",
                        "supported_robot_systems": ["paint"],
                        "ros_backend": {"launch_script": ""},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "ros_backend.launch_script"):
                load_startup_config(config_path)

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

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.bootstrap.ros_backend_launcher import (
    RosBackendLauncher,
    _clean_ros_process_env,
    build_ros_backend_launcher_from_env,
)
from src.bootstrap.startup_config import RosBackendConfig


class TestRosBackendLauncher(unittest.TestCase):
    def _script(self, directory: Path, name: str) -> Path:
        path = directory / name
        path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_start_launches_script_with_delay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = self._script(root, "launch.sh")
            stop = self._script(root, "stop.sh")
            process = MagicMock()
            process.poll.return_value = None

            with (
                patch("src.bootstrap.ros_backend_launcher.urllib.request.urlopen", side_effect=OSError("down")),
                patch("src.bootstrap.ros_backend_launcher.subprocess.Popen", return_value=process) as popen,
                patch("src.bootstrap.ros_backend_launcher.time.sleep") as sleep,
            ):
                launcher = RosBackendLauncher(launch, stop, startup_delay_s=1.5, log_file=root / "backend.log")
                launcher.start()
                launcher._close_log_handle()

            popen.assert_called_once_with(
                [str(launch)],
                cwd=str(root),
                start_new_session=True,
                env=unittest.mock.ANY,
                stdout=unittest.mock.ANY,
                stderr=subprocess.STDOUT,
            )
            env = popen.call_args.kwargs["env"]
            self.assertNotIn("VIRTUAL_ENV", env)
            self.assertNotIn("PYTHONPATH", env)
            self.assertEqual(Path(popen.call_args.kwargs["stdout"].name), root / "backend.log")
            sleep.assert_called_once_with(1.5)

    def test_stop_runs_stop_script_and_waits_for_launch_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = self._script(root, "launch.sh")
            stop = self._script(root, "stop.sh")
            process = MagicMock()
            process.poll.return_value = None

            with (
                patch("src.bootstrap.ros_backend_launcher.urllib.request.urlopen", side_effect=OSError("down")),
                patch("src.bootstrap.ros_backend_launcher.subprocess.Popen", return_value=process),
                patch("src.bootstrap.ros_backend_launcher.subprocess.run") as run,
                patch("src.bootstrap.ros_backend_launcher.time.sleep"),
            ):
                launcher = RosBackendLauncher(launch, stop, startup_delay_s=0, log_file=root / "backend.log")
                launcher.start()
                launcher.stop()

            run.assert_called_once_with(
                [str(stop)],
                cwd=str(root),
                check=False,
                timeout=30,
                env=unittest.mock.ANY,
            )
            process.wait.assert_called_once_with(timeout=10)
            self.assertIsNone(launcher._log_handle)

    def test_start_skips_launch_when_backend_is_already_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = self._script(root, "launch.sh")
            stop = self._script(root, "stop.sh")
            response = MagicMock()
            response.__enter__.return_value = response

            with (
                patch("src.bootstrap.ros_backend_launcher.urllib.request.urlopen", return_value=response),
                patch("src.bootstrap.ros_backend_launcher.subprocess.Popen") as popen,
                patch("src.bootstrap.ros_backend_launcher.subprocess.run") as run,
            ):
                launcher = RosBackendLauncher(launch, stop, startup_delay_s=0, log_file=root / "backend.log")
                launcher.start()
                launcher.stop()

            popen.assert_not_called()
            run.assert_not_called()

    def test_clean_env_removes_python_virtualenv_contamination(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIRTUAL_ENV": "/tmp/app/.venv",
                "PYTHONPATH": "/tmp/app/src",
                "PYTHONHOME": "/tmp/python",
                "PATH": "/tmp/app/.venv/bin:/usr/bin:/bin",
            },
            clear=False,
        ):
            env = _clean_ros_process_env()

        self.assertNotIn("VIRTUAL_ENV", env)
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("PYTHONHOME", env)
        self.assertNotIn("/tmp/app/.venv/bin", env["PATH"].split(os.pathsep))
        self.assertIn("/usr/bin", env["PATH"].split(os.pathsep))
        self.assertIn("/bin", env["PATH"].split(os.pathsep))

    def test_start_can_be_disabled_by_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = self._script(root, "launch.sh")
            stop = self._script(root, "stop.sh")

            with (
                patch.dict(os.environ, {"ROBOT_APP_BACKEND_AUTOSTART": "0"}),
                patch("src.bootstrap.ros_backend_launcher.subprocess.Popen") as popen,
            ):
                RosBackendLauncher(launch, stop).start()

            popen.assert_not_called()

    def test_start_can_be_disabled_by_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = self._script(root, "launch.sh")
            stop = self._script(root, "stop.sh")

            with patch("src.bootstrap.ros_backend_launcher.subprocess.Popen") as popen:
                RosBackendLauncher(launch, stop, auto_launch=False).start()

            popen.assert_not_called()

    def test_stop_can_be_disabled_by_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launch = self._script(root, "launch.sh")
            stop = self._script(root, "stop.sh")
            process = MagicMock()
            process.poll.return_value = None

            with (
                patch("src.bootstrap.ros_backend_launcher.urllib.request.urlopen", side_effect=OSError("down")),
                patch("src.bootstrap.ros_backend_launcher.subprocess.Popen", return_value=process),
                patch("src.bootstrap.ros_backend_launcher.subprocess.run") as run,
                patch("src.bootstrap.ros_backend_launcher.time.sleep"),
            ):
                launcher = RosBackendLauncher(launch, stop, startup_delay_s=0, log_file=root / "backend.log", auto_stop=False)
                launcher.start()
                launcher.stop()
                launcher._close_log_handle()

            run.assert_not_called()
            process.wait.assert_not_called()

    def test_builder_uses_config_defaults(self) -> None:
        launcher = build_ros_backend_launcher_from_env(
            RosBackendConfig(auto_launch=False, auto_stop=False)
        )

        self.assertFalse(launcher._auto_launch)
        self.assertFalse(launcher._auto_stop)


if __name__ == "__main__":
    unittest.main()

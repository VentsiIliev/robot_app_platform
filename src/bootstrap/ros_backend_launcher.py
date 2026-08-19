from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from src.bootstrap.startup_config import RosBackendConfig


_LOGGER = logging.getLogger(__name__)


class RosBackendLauncher:
    def __init__(
        self,
        launch_script: str | os.PathLike | None = None,
        stop_script: str | os.PathLike | None = None,
        startup_delay_s: float = 1.0,
        log_file: str | os.PathLike = "/tmp/robot_app_zeroerr_backend.log",
        status_urls: tuple[str, ...] = (
            "http://localhost:5000/startup/status",
            "http://localhost:5000/health",
        ),
        status_timeout_s: float = 0.3,
        auto_launch: bool = True,
        auto_stop: bool = True,
    ) -> None:
        self._launch_script = _expand_path(launch_script or _default_launch_script())
        self._stop_script = _expand_path(stop_script or _default_stop_script())
        self._startup_delay_s = float(startup_delay_s)
        self._log_file = _expand_path(log_file)
        self._status_urls = status_urls
        self._status_timeout_s = float(status_timeout_s)
        self._auto_launch = bool(auto_launch)
        self._auto_stop = bool(auto_stop)
        self._log_handle = None
        self._process: subprocess.Popen | None = None
        self._owns_backend = False

    def start(self) -> None:
        if not _env_enabled("ROBOT_APP_BACKEND_AUTOSTART", default=self._auto_launch):
            _LOGGER.info("ROS backend autostart disabled")
            return
        if self._process is not None and self._process.poll() is None:
            return
        if self._backend_is_reachable():
            _LOGGER.info("ROS backend is already reachable; skipping autostart")
            self._owns_backend = False
            return
        self._ensure_executable(self._launch_script)
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        self._log_handle = self._log_file.open("ab")
        _LOGGER.info("Starting ROS backend: %s (logs: %s)", self._launch_script, self._log_file)
        self._process = subprocess.Popen(
            [str(self._launch_script)],
            cwd=str(self._launch_script.parent),
            start_new_session=True,
            env=_clean_ros_process_env(),
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
        )
        self._owns_backend = True
        if self._startup_delay_s > 0:
            time.sleep(self._startup_delay_s)

    def stop(self) -> None:
        if not _env_enabled("ROBOT_APP_BACKEND_AUTOSTOP", default=self._auto_stop):
            _LOGGER.info("ROS backend autostop disabled")
            return
        if not self._owns_backend and self._process is None:
            _LOGGER.info("ROS backend was not started by this process; skipping autostop")
            return
        try:
            self._run_stop_script()
        finally:
            self._wait_for_launch_wrapper()
            self._close_log_handle()
            self._owns_backend = False

    def _backend_is_reachable(self) -> bool:
        for url in self._status_urls:
            try:
                with urllib.request.urlopen(url, timeout=self._status_timeout_s):
                    return True
            except urllib.error.HTTPError:
                return True
            except (OSError, urllib.error.URLError):
                continue
        return False

    def _run_stop_script(self) -> None:
        self._ensure_executable(self._stop_script)
        _LOGGER.info("Stopping ROS backend: %s", self._stop_script)
        subprocess.run(
            [str(self._stop_script)],
            cwd=str(self._stop_script.parent),
            check=False,
            timeout=30,
            env=_clean_ros_process_env(),
        )

    def _wait_for_launch_wrapper(self) -> None:
        process = self._process
        if process is None:
            return
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _LOGGER.warning("ROS backend launch wrapper did not exit after stop; terminating")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _LOGGER.warning("ROS backend launch wrapper did not terminate; killing")
                process.kill()
                process.wait(timeout=5)

    def _close_log_handle(self) -> None:
        if self._log_handle is None:
            return
        try:
            self._log_handle.close()
        finally:
            self._log_handle = None

    @staticmethod
    def _ensure_executable(path: Path) -> None:
        if not path.exists():
            raise RuntimeError(f"ROS backend script not found: {path}")
        if not os.access(path, os.X_OK):
            raise RuntimeError(f"ROS backend script is not executable: {path}")


def build_ros_backend_launcher_from_env(config: RosBackendConfig | None = None) -> RosBackendLauncher:
    config = config or RosBackendConfig()
    return RosBackendLauncher(
        launch_script=_value_from_env_or_config(
            "ROBOT_APP_BACKEND_LAUNCH_SCRIPT",
            config.launch_script,
            str(_default_launch_script()),
        ),
        stop_script=_value_from_env_or_config(
            "ROBOT_APP_BACKEND_STOP_SCRIPT",
            config.stop_script,
            str(_default_stop_script()),
        ),
        startup_delay_s=float(
            _value_from_env_or_config(
                "ROBOT_APP_BACKEND_STARTUP_DELAY_S",
                config.startup_delay_s,
                "1.0",
            )
        ),
        log_file=_value_from_env_or_config(
            "ROBOT_APP_BACKEND_LOG_FILE",
            config.log_file,
            "/tmp/robot_app_zeroerr_backend.log",
        ),
        status_urls=_status_urls_from_env(config.status_urls),
        status_timeout_s=float(
            _value_from_env_or_config(
                "ROBOT_APP_BACKEND_STATUS_TIMEOUT_S",
                config.status_timeout_s,
                "0.3",
            )
        ),
        auto_launch=config.auto_launch,
        auto_stop=config.auto_stop,
    )


def _default_launch_script() -> Path:
    return Path.home() / "ros2_ws" / "launch_zeroerr.sh"


def _default_stop_script() -> Path:
    return Path.home() / "ros2_ws" / "stop_zeroerr.sh"


def _expand_path(path: str | os.PathLike) -> Path:
    expanded = os.path.expandvars(os.fspath(path))
    return Path(expanded).expanduser()


def _value_from_env_or_config(name: str, config_value: object, default: str) -> str:
    env_value = os.environ.get(name)
    if env_value is not None:
        return env_value
    if config_value is not None:
        return str(config_value)
    return default


def _env_enabled(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _status_urls_from_env(config_urls: tuple[str, ...] | None = None) -> tuple[str, ...]:
    value = os.environ.get("ROBOT_APP_BACKEND_STATUS_URLS")
    if value is None and config_urls is not None:
        return config_urls
    if value is None:
        return _default_status_urls()
    urls = tuple(item.strip() for item in value.split(",") if item.strip())
    return urls or _default_status_urls()


def _default_status_urls() -> tuple[str, ...]:
    return (
        "http://localhost:5000/startup/status",
        "http://localhost:5000/health",
    )


def _clean_ros_process_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH"):
        env.pop(name, None)
    env["PATH"] = _clean_path(env.get("PATH", ""))
    return env


def _clean_path(path_value: str) -> str:
    system_paths = ["/usr/local/sbin", "/usr/local/bin", "/usr/sbin", "/usr/bin", "/sbin", "/bin"]
    blocked = {
        str(Path(sys.prefix) / "bin"),
        str(Path(sys.executable).resolve().parent),
    }
    parts = []
    for item in str(path_value or "").split(os.pathsep):
        if not item:
            continue
        resolved = str(Path(item).resolve())
        if resolved in blocked or resolved.endswith("/.venv/bin"):
            continue
        parts.append(item)
    for item in system_paths:
        if item not in parts:
            parts.append(item)
    return os.pathsep.join(parts)

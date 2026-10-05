"""Local, socket-activated controller for the system RustDesk unit.

Installed outside the application and run by systemd as root. The request
protocol deliberately has no command, unit-name, or path parameters.
"""

import json
import logging
import os
import socket
import subprocess
import time
from pathlib import Path


UNIT = "rustdesk.service"
STATE_DIR = Path("/var/lib/plproject/remote-support")
ENABLE_MARKER = STATE_DIR / "enabled"
MAX_REQUEST_BYTES = 1024
LOGGER = logging.getLogger("plproject.remote_support")


def _sync_state_directory() -> None:
    descriptor = os.open(STATE_DIR, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/usr/bin/systemctl", *args, UNIT],
        capture_output=True, text=True, timeout=30, check=False,
    )


def _status() -> dict:
    result = _systemctl("show", "--property=LoadState,ActiveState", "--no-pager")
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Cannot read RustDesk service state")
    values = dict(
        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
    )
    if values.get("LoadState") != "loaded":
        raise RuntimeError("RustDesk system service is not installed")
    active_state = values.get("ActiveState", "unknown")
    return {
        "enabled": ENABLE_MARKER.is_file(),
        "active": active_state == "active",
        "service_state": active_state,
    }


def _set_enabled(enabled: bool) -> dict:
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if enabled:
        _status()  # Do not persist ON for a missing or masked unit.
        # The marker gates service startup through ConditionPathExists.
        marker = STATE_DIR / ".enabled-new"
        with marker.open("w", encoding="ascii") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write("enabled\n")
            stream.flush()
            os.fsync(stream.fileno())
        marker.replace(ENABLE_MARKER)
        _sync_state_directory()
        # Enable at boot as well as starting now. OFF remains gated by the
        # systemd condition even when the unit is enabled.
        try:
            result = _systemctl("enable", "--now")
            status = _status()
            if result.returncode or not status["active"]:
                raise RuntimeError(result.stderr.strip() or "RustDesk service did not start")
            # Type=simple reports started before RustDesk has initialized.
            # Catch immediate shutdowns such as its own stop-service setting.
            time.sleep(1)
            status = _status()
            if not status["active"]:
                raise RuntimeError("RustDesk stopped during startup; check its service settings and logs")
            return status
        except (OSError, subprocess.SubprocessError, RuntimeError):
            ENABLE_MARKER.unlink(missing_ok=True)
            _sync_state_directory()
            try:
                _systemctl("stop")
            except (OSError, subprocess.SubprocessError):
                pass
            raise
    else:
        # Remove the startup permission before stopping a running session.
        ENABLE_MARKER.unlink(missing_ok=True)
        _sync_state_directory()
        result = _systemctl("stop")
    status = _status()
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Could not change RustDesk service")
    if status["active"] != enabled:
        raise RuntimeError("RustDesk service did not reach the requested state")
    return status


def handle_request(request: dict) -> dict:
    if not isinstance(request, dict) or set(request) != {"operation"}:
        raise ValueError("Invalid remote support request")
    operation = request["operation"]
    if operation == "status":
        return _status()
    if operation == "enable":
        LOGGER.info("Remote support enable requested")
        status = _set_enabled(True)
        LOGGER.info("Remote support enable completed: %s", status)
        return status
    if operation == "disable":
        LOGGER.info("Remote support disable requested")
        status = _set_enabled(False)
        LOGGER.info("Remote support disable completed: %s", status)
        return status
    raise ValueError("Unknown remote support operation")


def _serve_connection(connection: socket.socket) -> None:
    # A stalled local client must not block every subsequent status request.
    connection.settimeout(5)
    try:
        request_bytes = bytearray()
        while len(request_bytes) <= MAX_REQUEST_BYTES:
            chunk = connection.recv(1)
            if not chunk or chunk == b"\n":
                break
            request_bytes.extend(chunk)
        if not request_bytes or len(request_bytes) > MAX_REQUEST_BYTES:
            raise ValueError("Invalid remote support request size")
        result = {"ok": True, "status": handle_request(json.loads(request_bytes))}
    except (ValueError, OSError, subprocess.SubprocessError, RuntimeError) as exc:
        LOGGER.error("Remote support request failed: %s", exc)
        result = {"ok": False, "error": str(exc)}
    try:
        connection.sendall(json.dumps(result).encode("utf-8") + b"\n")
    except OSError:
        # A disconnected client must not terminate the root controller.
        pass


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(levelname)s: %(message)s")
    if os.geteuid() != 0 or os.environ.get("LISTEN_PID") != str(os.getpid()) or os.environ.get("LISTEN_FDS") != "1":
        raise SystemExit("Run via plproject-remote-support.socket as root")
    with socket.socket(fileno=3) as listener:
        while True:
            with listener.accept()[0] as connection:
                _serve_connection(connection)


if __name__ == "__main__":
    main()

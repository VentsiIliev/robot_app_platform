"""OS command adapter for network settings. No Qt code runs in this layer."""

import ipaddress
import re
import sys

from .i_network_settings_service import INetworkSettingsService
from .network_backend import LinuxBackend, WindowsBackend, run_command
from .remote_support_client import RemoteSupportClient


class NetworkSettingsService(INetworkSettingsService):
    def __init__(self, backend=None, platform: str | None = None, remote_support_client=None) -> None:
        self._platform = platform or sys.platform
        self._remote_support_client = remote_support_client or RemoteSupportClient()
        if backend is not None:
            self._backend = backend
        elif self._platform == "win32":
            self._backend = WindowsBackend()
        elif self._platform.startswith("linux"):
            self._backend = LinuxBackend()
        else:
            raise RuntimeError("Network settings are supported on Linux and Windows")

    def scan_wifi(self) -> list[dict]:
        return self._backend.scan_wifi()

    def list_wired(self) -> list[dict]:
        return self._backend.get_wired()

    def connect_wifi(self, ssid: str, password: str, secure: bool) -> None:
        if secure and not password:
            raise ValueError("Enter the Wi-Fi password")
        if self._platform == "win32":
            self._backend.connect_wifi(ssid, password, secure)
        else:
            self._backend.connect_wifi(ssid, password or None)

    def disconnect_wifi(self) -> None:
        self._backend.disconnect_wifi()

    def forget_wifi(self, ssid: str) -> None:
        self._backend.forget_wifi(ssid)

    def connect_wired(self, device: str) -> None:
        self._backend.connect_device(device)

    def disconnect_wired(self, device: str) -> None:
        self._backend.disconnect_device(device)

    def get_wifi_ipv4(self) -> dict:
        if self._platform == "win32":
            result = run_command(["netsh", "wlan", "show", "interfaces"])
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
            match = re.search(r"^\s*Name\s*:\s*(.+)$", result.stdout, re.MULTILINE)
            target = match.group(1).strip() if match else ""
        else:
            target = next(
                (device["connection"] for device in self._backend.get_devices()
                 if device["type"] == "wifi" and device["state"] == "connected"),
                "",
            )
        if not target or target == "--":
            raise RuntimeError("Connect to a Wi-Fi network first")
        return {"target": target, "settings": self._backend.get_connection_settings(target)}

    def get_wired_ipv4(self, device: dict) -> dict:
        target = device.get("device") if self._platform == "win32" else device.get("connection")
        if not target or target == "--":
            raise RuntimeError("Connect the wired interface first")
        return {"target": target, "settings": self._backend.get_connection_settings(target)}

    def apply_ipv4(self, target: str, settings: dict) -> None:
        mode = settings.get("mode")
        if mode not in ("auto", "manual"):
            raise ValueError("Select automatic or manual IPv4 mode")
        if mode == "manual":
            try:
                ipaddress.IPv4Address(settings.get("ip", ""))
            except ipaddress.AddressValueError as exc:
                raise ValueError("Enter a valid IPv4 address") from exc
            try:
                prefix = int(settings.get("prefix", ""))
            except (TypeError, ValueError) as exc:
                raise ValueError("Prefix must be between 0 and 32") from exc
            if not 0 <= prefix <= 32:
                raise ValueError("Prefix must be between 0 and 32")
            gateway = settings.get("gateway", "")
            if gateway:
                try:
                    ipaddress.IPv4Address(gateway)
                except ipaddress.AddressValueError as exc:
                    raise ValueError("Enter a valid gateway address") from exc
        for value in settings.get("dns", "").split(","):
            if value.strip():
                try:
                    ipaddress.ip_address(value.strip())
                except ValueError as exc:
                    raise ValueError(f"Invalid DNS server: {value.strip()}") from exc
        self._backend.apply_settings(target, settings)

    def get_remote_support_status(self) -> dict:
        if not self._platform.startswith("linux"):
            raise RuntimeError("Remote support service control is available on Linux")
        return self._remote_support_client.status()

    def set_remote_support_enabled(self, enabled: bool) -> dict:
        if not self._platform.startswith("linux"):
            raise RuntimeError("Remote support service control is available on Linux")
        return self._remote_support_client.set_enabled(enabled)

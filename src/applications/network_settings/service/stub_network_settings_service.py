from .i_network_settings_service import INetworkSettingsService


class StubNetworkSettingsService(INetworkSettingsService):
    """In-memory adapter for standalone previews and application tests."""

    def __init__(self) -> None:
        self.wifi = [
            {"ssid": "Workshop", "signal": "84", "strength": 84, "secure": True, "connected": True},
            {"ssid": "Guest", "signal": "62", "strength": 62, "secure": False, "connected": False},
        ]
        self.wired = [{"device": "eth0", "state": "connected", "connection": "Wired connection 1"}]
        self.ipv4 = {"mode": "auto", "ip": "", "prefix": "24", "gateway": "", "dns": ""}
        self.remote_support_enabled = False

    def scan_wifi(self) -> list[dict]: return list(self.wifi)
    def list_wired(self) -> list[dict]: return list(self.wired)
    def connect_wifi(self, ssid: str, password: str, secure: bool) -> None:
        for network in self.wifi: network["connected"] = network["ssid"] == ssid
    def disconnect_wifi(self) -> None:
        for network in self.wifi: network["connected"] = False
    def forget_wifi(self, ssid: str) -> None:
        self.wifi = [network for network in self.wifi if network["ssid"] != ssid]
    def connect_wired(self, device: str) -> None: self.wired[0]["state"] = "connected"
    def disconnect_wired(self, device: str) -> None: self.wired[0]["state"] = "disconnected"
    def get_wifi_ipv4(self) -> dict: return {"target": "Workshop", "settings": dict(self.ipv4)}
    def get_wired_ipv4(self, device: dict) -> dict: return {"target": device["connection"], "settings": dict(self.ipv4)}
    def apply_ipv4(self, target: str, settings: dict) -> None: self.ipv4 = dict(settings)
    def get_remote_support_status(self) -> dict:
        return {"enabled": self.remote_support_enabled, "active": self.remote_support_enabled,
                "service_state": "active" if self.remote_support_enabled else "inactive"}
    def set_remote_support_enabled(self, enabled: bool) -> dict:
        self.remote_support_enabled = bool(enabled)
        return self.get_remote_support_status()

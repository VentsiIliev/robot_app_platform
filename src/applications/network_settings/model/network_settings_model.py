from src.applications.base.i_application_model import IApplicationModel
from src.applications.network_settings.service.i_network_settings_service import INetworkSettingsService


class NetworkSettingsModel(IApplicationModel):
    def __init__(self, service: INetworkSettingsService) -> None:
        self._service = service

    def load(self) -> None:
        """The controller schedules network discovery after the page is shown."""

    def save(self, target: str, settings: dict) -> None:
        self._service.apply_ipv4(target, settings)

    def scan_wifi(self) -> list[dict]: return self._service.scan_wifi()
    def list_wired(self) -> list[dict]: return self._service.list_wired()
    def connect_wifi(self, ssid: str, password: str, secure: bool) -> None:
        self._service.connect_wifi(ssid, password, secure)
    def disconnect_wifi(self) -> None: self._service.disconnect_wifi()
    def forget_wifi(self, ssid: str) -> None: self._service.forget_wifi(ssid)
    def connect_wired(self, device: str) -> None: self._service.connect_wired(device)
    def disconnect_wired(self, device: str) -> None: self._service.disconnect_wired(device)
    def get_wifi_ipv4(self) -> dict: return self._service.get_wifi_ipv4()
    def get_wired_ipv4(self, device: dict) -> dict: return self._service.get_wired_ipv4(device)
    def get_remote_support_status(self) -> dict: return self._service.get_remote_support_status()
    def set_remote_support_enabled(self, enabled: bool) -> dict:
        return self._service.set_remote_support_enabled(enabled)

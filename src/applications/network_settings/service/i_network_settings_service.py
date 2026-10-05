"""Platform-independent contract for the shared Network Settings application."""

from abc import ABC, abstractmethod


class INetworkSettingsService(ABC):
    @abstractmethod
    def scan_wifi(self) -> list[dict]: ...

    @abstractmethod
    def list_wired(self) -> list[dict]: ...

    @abstractmethod
    def connect_wifi(self, ssid: str, password: str, secure: bool) -> None: ...

    @abstractmethod
    def disconnect_wifi(self) -> None: ...

    @abstractmethod
    def forget_wifi(self, ssid: str) -> None: ...

    @abstractmethod
    def connect_wired(self, device: str) -> None: ...

    @abstractmethod
    def disconnect_wired(self, device: str) -> None: ...

    @abstractmethod
    def get_wifi_ipv4(self) -> dict: ...

    @abstractmethod
    def get_wired_ipv4(self, device: dict) -> dict: ...

    @abstractmethod
    def apply_ipv4(self, target: str, settings: dict) -> None: ...

    @abstractmethod
    def get_remote_support_status(self) -> dict: ...

    @abstractmethod
    def set_remote_support_enabled(self, enabled: bool) -> dict: ...

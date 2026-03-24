from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from src.shared_contracts.declarations import DispenseChannelDefinition


class IDispenseChannelSettingsService(ABC):
    @abstractmethod
    def get_channel_definitions(self) -> List[DispenseChannelDefinition]: ...

    @abstractmethod
    def get_available_glue_types(self) -> List[str]: ...

    @abstractmethod
    def get_channel_flat(self, channel_id: str) -> Optional[dict]: ...

    @abstractmethod
    def save_channel(self, channel_id: str, flat: dict) -> None: ...

    @abstractmethod
    def tare(self, channel_id: str) -> bool: ...

    @abstractmethod
    def start_pump_test(self, channel_id: str) -> bool: ...

    @abstractmethod
    def stop_pump_test(self, channel_id: str) -> bool: ...

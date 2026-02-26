from abc import ABC, abstractmethod
from typing import List

from src.engine.hardware.modbus import ModbusConfig


class IModbusSettingsService(ABC):

    @abstractmethod
    def load_config(self) -> ModbusConfig: ...

    @abstractmethod
    def save_config(self, config: ModbusConfig) -> None: ...

    @abstractmethod
    def detect_ports(self) -> List[str]:
        """Return list of available serial port names."""
        ...

    @abstractmethod
    def test_connection(self, config: ModbusConfig) -> bool:
        """Attempt a connection with the given config. Return True on success."""
        ...

from abc import ABC, abstractmethod
from typing import List

from src.engine.hardware.communication.modbus.modbus import ModbusConfig


class IModbusActionService(ABC):

    @abstractmethod
    def detect_ports(self) -> List[str]:
        """Return available serial port names that have a modbus device."""
        ...

    @abstractmethod
    def test_connection(self, config: ModbusConfig) -> bool:
        """Attempt a connection with the given config. Return True on success."""
        ...
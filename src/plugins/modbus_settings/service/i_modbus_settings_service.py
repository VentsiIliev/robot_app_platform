from abc import ABC, abstractmethod

from src.engine.hardware.communication.modbus.modbus import ModbusConfig


class IModbusSettingsService(ABC):

    @abstractmethod
    def load_config(self) -> ModbusConfig: ...

    @abstractmethod
    def save_config(self, config: ModbusConfig) -> None: ...

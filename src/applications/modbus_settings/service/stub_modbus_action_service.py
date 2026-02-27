from typing import List

from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService
from src.engine.hardware.communication.modbus.modbus import ModbusConfig


class StubModbusActionService(IModbusActionService):

    def detect_ports(self) -> List[str]:
        print("[StubModbusActionService] detect_ports")
        return ["COM1", "COM3", "COM5", "/dev/ttyUSB0", "/dev/ttyUSB1"]

    def test_connection(self, config: ModbusConfig) -> bool:
        print(f"[StubModbusActionService] test_connection → port={config.port}")
        return True
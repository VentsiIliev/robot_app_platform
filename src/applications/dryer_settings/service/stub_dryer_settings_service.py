from __future__ import annotations

from typing import Dict, List

from src.applications.dryer_settings.service.i_dryer_settings_service import IDryerSettingsService
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.dryer.dryer_controller import DryerController
from src.engine.hardware.dryer.interfaces.i_dryer_transport import IDryerTransport
from src.engine.hardware.dryer.models.dryer_commands import DryerStatus
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_state import DryerState
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData


class MockDryerTransport(IDryerTransport):
    def __init__(self) -> None:
        self.registers: Dict[int, int] = {}
        self.writes: List[tuple[int, List[int]]] = []

    def read_register(self, address: int) -> int:
        return self.registers.get(address, 0)

    def write_register(self, address: int, value: int) -> None:
        self.registers[address] = int(value)
        self.writes.append((address, [int(value)]))

    def write_registers(self, address: int, values: List[int]) -> None:
        clean_values = [int(value) for value in values]
        for index, value in enumerate(clean_values):
            self.registers[address + index] = value
        self.writes.append((address, clean_values))


class StubDryerSettingsService(IDryerSettingsService):
    def __init__(
        self,
        modbus_config: ModbusConfig | None = None,
        dryer_config: DryerConfig | None = None,
    ) -> None:
        self.modbus_config = modbus_config or ModbusConfig(
            port="/dev/ttyUSB0",
            baudrate=115200,
            bytesize=8,
            stopbits=1,
            parity="N",
            timeout=0.03,
            slave_address=10,
            max_retries=3,
        )
        self._config = dryer_config or DryerConfig(
            status_register=100,
            command_register=101,
            delay_move_up_register=102,
            delay_move_down_register=103,
            delay_move_in_register=104,
            delay_move_out_register=105,
            speed_of_plates_register=106,
            default_delay_move_up=120,
            default_delay_move_down=140,
            default_delay_move_in=80,
            default_delay_move_out=90,
            default_speed_of_plates=50,
        )
        self.transport = MockDryerTransport()
        self.transport.registers[self._config.status_register] = int(
            DryerStatus.READY | DryerStatus.PLATE_ON_POSITION
        )

    def load_config(self) -> DryerConfig:
        return self._config

    def save_config(self, config: DryerConfig) -> None:
        self._config = config
        self.transport.registers.setdefault(
            self._config.status_register,
            int(DryerStatus.READY | DryerStatus.PLATE_ON_POSITION),
        )

    def get_state(self, config: DryerConfig) -> DryerState:
        return self._controller(config).get_state()

    def move_servos(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._controller(config).move_servos(data)

    def open_plate(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._controller(config).open_plate(data)

    def close_plate(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._controller(config).close_plate(data)

    def next_position(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._controller(config).next_position(data)

    def _controller(self, config: DryerConfig) -> DryerController:
        return DryerController(self.transport, config)

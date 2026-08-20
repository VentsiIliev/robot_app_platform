"""
Dryer controller mock runner — manual integration / smoke example.

No serial port required. MockDryerTransport intercepts register I/O while the
controller is constructed with the same config objects used by real wiring.
"""

from __future__ import annotations

import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.dryer.dryer_controller import DryerController
from src.engine.hardware.dryer.interfaces.i_dryer_transport import IDryerTransport
from src.engine.hardware.dryer.models.dryer_commands import DryerStatus
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData


class MockDryerTransport(IDryerTransport):
    def __init__(self) -> None:
        self.registers: Dict[int, int] = {}
        self.writes: List[tuple[int, List[int]]] = []
        self.connected = False

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

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False


def _print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def _print_mapping(mapping: Dict[str, Any]) -> None:
    width = max(len(str(key)) for key in mapping)
    for key, value in mapping.items():
        print(f"  {key:<{width}} : {value}")


def _print_dataclass(title: str, value: Any) -> None:
    _print_section(title)
    if not is_dataclass(value):
        print(f"  {value}")
        return
    _print_mapping(asdict(value))


def run_mock() -> None:
    modbus_config = ModbusConfig(
        port="/dev/ttyUSB0",
        baudrate=115200,
        bytesize=8,
        stopbits=1,
        parity="N",
        timeout=0.03,
        slave_address=10,
        max_retries=3,
    )
    dryer_config = DryerConfig()

    transport = MockDryerTransport()
    transport.connect()
    controller = DryerController(
        transport=transport,
        config=dryer_config,
    )

    transport.registers[0] = int(
        DryerStatus.READY | DryerStatus.PLATE_ON_POSITION
    )

    _print_dataclass("Modbus Config", modbus_config)
    _print_dataclass("Dryer Config", dryer_config)
    _print_dataclass("Initial State", controller.get_state())

    controller.move_servos()
    controller.open_plate(
        DryerWriteData.from_config(dryer_config)
    )
    controller.next_position()

    _print_section("Register Writes")
    for index, (address, values) in enumerate(transport.writes, start=1):
        print(f"  #{index}")
        print(f"    start_register : {address}")
        print(f"    values         : {values}")

    _print_section("Register Map")
    _print_mapping({str(key): value for key, value in sorted(transport.registers.items())})
    transport.disconnect()


if __name__ == "__main__":
    run_mock()

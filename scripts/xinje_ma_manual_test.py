#!/usr/bin/env python3
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_transport import (
    ModbusVacuumPumpTransport,
)
from src.engine.hardware.xinje import XinjeMA8X8YR

# Edit these values directly for manual hardware testing.
PORT = "/dev/ttyUSB0"
SLAVE_ADDRESS = 1
BAUDRATE = 57600
BYTESIZE = 8
PARITY = "E"
STOPBITS = 1
TIMEOUT = 0.5


transport = ModbusVacuumPumpTransport(
    port=PORT,
    slave_address=SLAVE_ADDRESS,
    baudrate=BAUDRATE,
    bytesize=BYTESIZE,
    parity=PARITY,
    stopbits=STOPBITS,
    timeout=TIMEOUT,
)


def read_input(point: str | int) -> int:
    address = XinjeMA8X8YR.resolve_input(point)
    value = transport.read_register(address)
    print(f"read_input({point!r}) address={address} -> {value}")
    return value


def read_output(point: str | int) -> int:
    address = XinjeMA8X8YR.resolve_output(point)
    value = transport.read_register(address)
    print(f"read_output({point!r}) address={address} -> {value}")
    return value


def write_output(point: str | int, value: int | bool) -> None:
    address = XinjeMA8X8YR.resolve_output(point)
    bit = 1 if value else 0
    print(f"write_output({point!r}, {bit}) address={address}")
    transport.write_register(address, bit)


def pulse_output(point: str | int, hold_s: float = 1.0) -> None:
    write_output(point, 1)
    time.sleep(max(0.0, hold_s))
    write_output(point, 0)


def read_all_inputs() -> dict[str, int]:
    values = {}
    for index in range(8):
        point = f"X{index}"
        values[point] = read_input(point)
    return values


def read_all_outputs() -> dict[str, int]:
    values = {}
    for index in range(8):
        point = f"Y{index}"
        values[point] = read_output(point)
    return values


if __name__ == "__main__":
    print(
        f"Xinje MA manual test on {PORT} slave={SLAVE_ADDRESS} "
        f"{BAUDRATE},{BYTESIZE}{PARITY}{STOPBITS}"
    )

    # Edit these calls directly while testing hardware.
    while True:
        read_all_inputs()
        # read_all_outputs()
        time.sleep(1)

    # count = 10
    # while count > 0:
    #     iteration = 11 - count
    #     count -= 1
    #     print(f"Pulse Y0, iteration {iteration}")
    #
    #     try:
    #         pulse_output("Y5", hold_s=1.0)
    #     except Exception as exc:
    #         print(f"Pulse Y0 failed on iteration {iteration}: {exc}")
    #
    #     time.sleep(0.2)

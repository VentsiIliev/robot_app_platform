"""Read all Xinje MA-8X8YR inputs and outputs.

Run from the repository root:
    .venv/bin/python scripts/read_xinje_io.py

The script uses the configured Xinje slave from Paint's Modbus settings and
does not write any outputs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY
from src.engine.hardware.xinje import XinjeMA8X8YR


SETTINGS_DIR = (
    ROOT
    / "src"
    / "robot_systems"
    / "paint"
    / "storage"
    / "settings"
    / "hardware"
)
MODBUS_PATH = SETTINGS_DIR / "modbus.json"


def load_modbus_config() -> ModbusConfig:
    with MODBUS_PATH.open("r", encoding="utf-8") as stream:
        return ModbusConfig.from_dict(json.load(stream))


def main() -> None:
    config = load_modbus_config()
    slave_name = "xinje_ma"
    slave = config.get_slave(slave_name)
    connection = config.get_connection(slave_name)
    transport = DEFAULT_TRANSPORT_REGISTRY.build_for_slave(config, slave_name)

    print(f"Configuration: {MODBUS_PATH}")
    print(
        f"Xinje slave={connection.slave_address} profile={slave.profile_name} "
        f"transport={slave.transport_type} "
        f"serial={connection.port} {connection.baudrate},"
        f"{connection.bytesize}{connection.parity}{connection.stopbits}"
    )
    print("Reading inputs and outputs with Modbus FC1; no writes will be performed.")

    inputs = transport.read_registers(XinjeMA8X8YR.resolve_input("X0"), 8)
    outputs = transport.read_registers(XinjeMA8X8YR.resolve_output("Y0"), 8)

    print("Inputs:")
    for index, value in enumerate(inputs):
        print(f"  X{index} (address {index}): {bool(value)}")

    print("Outputs:")
    for index, value in enumerate(outputs):
        address = XinjeMA8X8YR.resolve_output(f"Y{index}")
        print(f"  Y{index} (address {address}): {bool(value)}")


if __name__ == "__main__":
    main()

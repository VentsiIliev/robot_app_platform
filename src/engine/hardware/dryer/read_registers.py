"""Write diagnostic value 2 to address 2, then print all dryer registers.

It uses the same Paint Modbus and peripheral settings, transport registry, and
dryer register map as the runtime.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPOSITORY_ROOT))

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.transport_registry import (
    DEFAULT_TRANSPORT_REGISTRY,
)
from src.engine.hardware.dryer.models.dryer_status import DryerStatus
from src.engine.hardware.dryer.models.dryer_modbus_registers import (
    DryerRegisterMap,
)
from src.engine.hardware.peripherals import PeripheralConfig


DEFAULT_MODBUS_PATH = (
    REPOSITORY_ROOT
    / "src/robot_systems/paint/storage/settings/hardware/modbus.json"
)
DEFAULT_PERIPHERALS_PATH = (
    REPOSITORY_ROOT
    / "src/robot_systems/paint/storage/settings/hardware/peripherals.json"
)


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_all_registers(modbus_path: Path, peripherals_path: Path) -> None:
    modbus_config = ModbusConfig.from_dict(_load_json(modbus_path))
    peripheral_config = PeripheralConfig.from_dict(_load_json(peripherals_path))
    binding = peripheral_config.peripherals.get("dryer")
    if binding is None:
        raise RuntimeError(f"dryer is not configured in {peripherals_path}")

    register_map = DryerRegisterMap.from_mapping({**binding.inputs, **binding.outputs})
    register_map.require_contiguous()
    slave_name = modbus_config.find_slave_name(binding.slave_id)
    connection = modbus_config.get_connection(slave_name)
    transport = DEFAULT_TRANSPORT_REGISTRY.build_for_slave(modbus_config, slave_name)

    print(
        f"Dryer: port={connection.port} slave={connection.slave_address} "
        f"baud={connection.baudrate} parity={connection.parity} "
        f"timeout={connection.timeout}s"
    )
    try:
        print("Writing value 2 to holding register address 2...")
        transport.write_register(2, 600)
        transport.write_register(1, 0)
        print("Write acknowledged.")
        print(
            f"Reading {len(register_map.addresses)} holding registers "
            f"from address {register_map.status}..."
        )
        values = transport.read_registers(
            register_map.status,
            len(register_map.addresses),
        )
    finally:
        transport.disconnect()

    print()
    print(f"{'ADDRESS':>7}  {'REGISTER':<38} {'DECIMAL':>7}  HEX")
    print(f"{'-' * 7}  {'-' * 38} {'-' * 7}  {'-' * 6}")
    for name, address, value in zip(
        register_map.__dataclass_fields__,
        register_map.addresses,
        values,
    ):
        print(f"{address:>7}  {name:<38} {int(value):>7}  0x{int(value) & 0xFFFF:04X}")

    status = int(values[0])
    flags = [flag.name for flag in DryerStatus if status & int(flag)]
    print()
    print(f"Decoded status: {', '.join(flags) if flags else 'no status flags set'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--modbus-config",
        type=Path,
        default=DEFAULT_MODBUS_PATH,
        help=f"Modbus settings JSON (default: {DEFAULT_MODBUS_PATH})",
    )
    parser.add_argument(
        "--peripherals-config",
        type=Path,
        default=DEFAULT_PERIPHERALS_PATH,
        help=f"Peripheral settings JSON (default: {DEFAULT_PERIPHERALS_PATH})",
    )
    args = parser.parse_args()

    try:
        read_all_registers(args.modbus_config, args.peripherals_config)
    except Exception as exc:
        print(f"Dryer register read failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

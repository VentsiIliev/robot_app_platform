"""Move by a specified angle using the compact paint Modbus config."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.transport_registry import (
    DEFAULT_TRANSPORT_REGISTRY,
)


MIN_WRITE_VALUE=45


REGISTER_ADDRESS = 2

# Edit this relative movement, then run the script normally from PyCharm.
# Use a negative value to move in the opposite direction.
MOVE_DEGREES = 10

# Device calibration: 0 degrees = 47, 90 degrees = 141.
MIN_DEGREES = 0.0
MAX_DEGREES = 90.0
MIN_REGISTER_VALUE = 47
MAX_REGISTER_VALUE = 141
MODBUS_CONFIG_PATH = (
    REPOSITORY_ROOT
    / "src/robot_systems/paint/profiles/tray_dryer/storage/settings/hardware/modbus.json"
)


def degrees_to_register_delta(degrees: float) -> int:
    register_units_per_degree = (
        (MAX_REGISTER_VALUE - MIN_REGISTER_VALUE)
        / (MAX_DEGREES - MIN_DEGREES)
    )
    return round(degrees * register_units_per_degree)


def main() -> int:
    with MODBUS_CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        config = ModbusConfig.from_dict(json.load(config_file))

    slave_name = "default"
    connection = config.get_connection(slave_name)
    transport = DEFAULT_TRANSPORT_REGISTRY.build_for_slave(config, slave_name)

    current_value = transport.read_register(REGISTER_ADDRESS)
    # register_delta = degrees_to_register_delta(MOVE_DEGREES)
    # value_to_write = current_value + register_delta
    setting=2
    step=10
    value_to_write = 45+(step*(6-setting))
    if value_to_write < MIN_WRITE_VALUE:
        raise ValueError(
            f"Relative move is outside the calibrated range: current value "
            f"{current_value} + delta {value_to_write-current_value} = {value_to_write}; "
            f"allowed range is {MIN_WRITE_VALUE}..{MAX_REGISTER_VALUE}"
        )
    # if not MIN_REGISTER_VALUE <= value_to_write <= MAX_REGISTER_VALUE:
    #     raise ValueError(
    #         f"Relative move is outside the calibrated range: current value "
    #         f"{current_value} + delta {register_delta} = {value_to_write}; "
    #         f"allowed range is {MIN_REGISTER_VALUE}..{MAX_REGISTER_VALUE}"
    #     )
    #
    # print(
    #     f"Moving by {MOVE_DEGREES:+.1f} degrees: current value {current_value}, "
    #     f"delta {register_delta:+d}, new value {value_to_write}; writing "
    #     f"to holding register {REGISTER_ADDRESS} "
    #     f"on {connection.port}, slave {connection.slave_address}..."
    # )
    # Do not catch exceptions here: PyCharm should show the complete traceback
    # for configuration, serial-port, timeout, or Modbus protocol failures.
    # write_register() uses a per-call session and closes it before returning.
    transport.write_register(REGISTER_ADDRESS, value_to_write)

    value_read_back = transport.read_register(REGISTER_ADDRESS)
    print(f"Read back holding register {REGISTER_ADDRESS}: {value_read_back}")
    if value_read_back != value_to_write:
        raise RuntimeError(
            f"Readback mismatch: wrote {value_to_write}, read {value_read_back}"
        )

    print(f"Relative move by {MOVE_DEGREES:+.1f} degrees acknowledged and verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

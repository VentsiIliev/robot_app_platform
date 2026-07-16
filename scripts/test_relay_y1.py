#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_transport import (
    ModbusVacuumPumpTransport,
)

DEFAULT_CONFIG = ROOT / "src" / "robot_systems" / "paint" / "storage" / "settings" / "hardware" / "modbus.json"
DEFAULT_REGISTER = 129  # Y1. Existing pump output is 128.


def _load_modbus_config(path: Path) -> ModbusConfig:
    with path.open("r", encoding="utf-8") as fh:
        return ModbusConfig.from_dict(json.load(fh))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test the Y1 relay output without touching the pump output.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=f"Modbus JSON path. Default: {DEFAULT_CONFIG}")
    parser.add_argument("--port", help="Override serial port from config, e.g. /dev/ttyUSB0")
    parser.add_argument("--register", type=int, default=DEFAULT_REGISTER, help=f"Relay coil/register address. Default: {DEFAULT_REGISTER} (Y1)")
    parser.add_argument("--hold", type=float, default=10.0, help="How long to keep the relay ON before turning it OFF. Default: 10.0")
    parser.add_argument("--repeat", type=int, default=1, help="How many ON/OFF pulses to send. Default: 1")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between pulses in seconds. Default: 0.5")
    return parser.parse_args()


def _build_transport(config: ModbusConfig) -> ModbusVacuumPumpTransport:
    return ModbusVacuumPumpTransport(
        port=config.port,
        slave_address=config.slave_address,
        baudrate=config.baudrate,
        bytesize=config.bytesize,
        stopbits=config.stopbits,
        parity=config.parity,
        timeout=config.timeout,
    )


def main() -> int:
    args = _parse_args()
    config = _load_modbus_config(args.config)
    if args.port:
        config.port = args.port

    transport = _build_transport(config)
    register = int(args.register)
    hold = max(0.0, float(args.hold))
    repeat = max(1, int(args.repeat))
    delay = max(0.0, float(args.delay))

    print(f"Testing relay register {register}")
    all_ok = True
    for index in range(repeat):
        try:
            transport.write_register(register, 1)
            print(f"ON command {index + 1}/{repeat}: ok")
            print(f"Relay should be ON for {hold:.1f} seconds now")
            if hold > 0:
                time.sleep(hold)
            transport.write_register(register, 0)
            print(f"OFF command {index + 1}/{repeat}: ok")
        except Exception as exc:
            all_ok = False
            print(f"Relay test {index + 1}/{repeat}: failed ({exc})")

        if index + 1 < repeat and delay > 0:
            time.sleep(delay)

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

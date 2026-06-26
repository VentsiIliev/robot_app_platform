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
from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig
from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_factory import (
    build_modbus_vacuum_pump_controller,
)

DEFAULT_CONFIG = ROOT / "src" / "robot_systems" / "paint" / "storage" / "settings" / "hardware" / "modbus.json"


def _load_modbus_config(path: Path) -> ModbusConfig:
    with path.open("r", encoding="utf-8") as fh:
        return ModbusConfig.from_dict(json.load(fh))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send direct OFF commands to the paint vacuum pump relay.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=f"Modbus JSON path. Default: {DEFAULT_CONFIG}")
    parser.add_argument("--port", help="Override serial port from config, e.g. /dev/ttyUSB0")
    parser.add_argument("--register", type=int, default=128, help="Vacuum pump coil/register address. Default: 128")
    parser.add_argument("--repeat", type=int, default=1, help="How many OFF commands to send. Default: 5")
    parser.add_argument("--delay", type=float, default=0.05, help="Delay between OFF commands in seconds. Default: 0.05")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = _load_modbus_config(args.config)
    if args.port:
        config.port = args.port

    controller = build_modbus_vacuum_pump_controller(
        modbus_config=config,
        vacuum_config=VacuumPumpConfig(pump_register=args.register),
    )

    repeat = max(1, int(args.repeat))
    delay = max(0.0, float(args.delay))
    all_ok = True
    for index in range(repeat):
        attempt_ok = controller.turn_on()
        time.sleep(1)
        attempt_ok = controller.turn_off()
        all_ok = attempt_ok and all_ok
        print(f"OFF command {index + 1}/{repeat}: {'ok' if attempt_ok else 'failed'}")
        if index + 1 < repeat and delay > 0:
            time.sleep(delay)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

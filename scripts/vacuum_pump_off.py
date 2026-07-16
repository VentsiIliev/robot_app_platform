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
DEFAULT_REGISTER = 128  # Existing pump output.
DEFAULT_BLOW_OFF_REGISTER = 129  # Y1 release valve output.
DEFAULT_BLOW_OFF_SECONDS = 0.2


def _load_modbus_config(path: Path) -> ModbusConfig:
    with path.open("r", encoding="utf-8") as fh:
        return ModbusConfig.from_dict(json.load(fh))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Turn the paint vacuum pump ON, wait, then turn it OFF.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=f"Modbus JSON path. Default: {DEFAULT_CONFIG}")
    parser.add_argument("--port", help="Override serial port from config, e.g. /dev/ttyUSB0")
    parser.add_argument("--register", type=int, default=DEFAULT_REGISTER, help=f"Vacuum pump coil/register address. Default: {DEFAULT_REGISTER}")
    parser.add_argument("--blow-off-register", type=int, default=DEFAULT_BLOW_OFF_REGISTER, help=f"Blow-off coil/register address. Default: {DEFAULT_BLOW_OFF_REGISTER}")
    parser.add_argument("--blow-off-seconds", type=float, default=DEFAULT_BLOW_OFF_SECONDS, help=f"How long to pulse blow-off after pump OFF. Default: {DEFAULT_BLOW_OFF_SECONDS}")
    parser.add_argument("--repeat", type=int, default=1, help="How many ON/OFF pulses to send. Default: 1")
    parser.add_argument("--hold", type=float, default=2.0, help="How long to keep the pump ON before turning it OFF. Default: 5.0")
    parser.add_argument("--delay", type=float, default=0.05, help="Delay between pulses in seconds. Default: 0.05")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = _load_modbus_config(args.config)
    if args.port:
        config.port = args.port

    repeat = max(1, int(args.repeat))
    hold = max(0.0, float(args.hold))
    delay = max(0.0, float(args.delay))
    all_ok = True
    blow_off_seconds = max(0.0, float(args.blow_off_seconds))
    print(
        f"Testing pump register {args.register}; "
        f"blow-off register {args.blow_off_register} for {blow_off_seconds:.3f}s"
    )

    controller = build_modbus_vacuum_pump_controller(
        modbus_config=config,
        vacuum_config=VacuumPumpConfig(
            pump_register=args.register,
            blow_off_register=args.blow_off_register,
            blow_off_pulse_seconds=blow_off_seconds,
        ),
    )
    for index in range(repeat):
        attempt_ok = controller.turn_on()
        all_ok = attempt_ok and all_ok
        print(f"ON command {index + 1}/{repeat}: {'ok' if attempt_ok else 'failed'}")
        print(f"Pump should be ON for {hold:.1f} seconds now")
        if hold > 0:
            time.sleep(hold)
        attempt_ok = controller.turn_off()
        all_ok = attempt_ok and all_ok
        print(f"OFF command {index + 1}/{repeat}: {'ok' if attempt_ok else 'failed'}")
        if index + 1 < repeat and delay > 0:
            time.sleep(delay)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

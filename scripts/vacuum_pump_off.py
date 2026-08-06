#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


# MODBUS CONFIG FOR THE XINJE/PUMP


# {
#     "port": "/dev/ttyUSB0",
#     "baudrate": 57600,
#     "bytesize": 8,
#     "stopbits": 1,
#     "parity": "E",
#     "timeout": 0.001,
#     "slave_address": 1,
#     "max_retries": 30
# }

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig
from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_factory import (
    build_modbus_vacuum_pump_controller,
)
from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_transport import (
    ModbusVacuumPumpTransport,
)

DEFAULT_CONFIG = ROOT / "src" / "robot_systems" / "paint" / "storage" / "settings" / "hardware" / "modbus.json"
DEFAULT_REGISTER = 128  # Relay output Y0 coil address.
DEFAULT_BLOW_OFF_REGISTER = 129  # Relay output Y1 release valve coil address.
DEFAULT_BLOW_OFF_SECONDS = 0.2


def _load_modbus_config(path: Path) -> ModbusConfig:
    with path.open("r", encoding="utf-8") as fh:
        return ModbusConfig.from_dict(json.load(fh))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Turn the paint vacuum pump ON, wait, then turn it OFF.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=f"Modbus JSON path. Default: {DEFAULT_CONFIG}")
    parser.add_argument("--port", help="Override serial port from config, e.g. /dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, help="Override serial baudrate from config.")
    parser.add_argument("--parity", choices=("N", "E", "O"), help="Override serial parity from config.")
    parser.add_argument("--slave", type=int, help="Override Modbus slave address from config.")
    parser.add_argument("--timeout", type=float, help="Override serial timeout from config.")
    parser.add_argument("--register", type=int, default=DEFAULT_REGISTER, help=f"Vacuum pump coil/register address. Default: {DEFAULT_REGISTER}")
    parser.add_argument("--blow-off-register", type=int, default=DEFAULT_BLOW_OFF_REGISTER, help=f"Blow-off coil/register address. Default: {DEFAULT_BLOW_OFF_REGISTER}")
    parser.add_argument("--blow-off-seconds", type=float, default=DEFAULT_BLOW_OFF_SECONDS, help=f"How long to pulse blow-off after pump OFF. Default: {DEFAULT_BLOW_OFF_SECONDS}")
    parser.add_argument("--readback", action="store_true", help="Read pump and blow-off coils before and after each command when supported.")
    parser.add_argument("--repeat", type=int, default=1, help="How many ON/OFF pulses to send. Default: 1")
    parser.add_argument("--hold", type=float, default=1.0, help="How long to keep the pump ON before turning it OFF. Default: 5.0")
    parser.add_argument("--delay", type=float, default=0.05, help="Delay between pulses in seconds. Default: 0.05")
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


def _print_readback(
    transport: ModbusVacuumPumpTransport,
    label: str,
    pump_register: int,
    blow_off_register: int,
) -> None:
    try:
        pump = transport.read_register(pump_register)
        blow_off = transport.read_register(blow_off_register)
    except Exception as exc:
        print(f"{label} readback failed: {exc}")
        return
    print(f"{label} readback: pump={pump} blow_off={blow_off}")


def main() -> int:
    args = _parse_args()
    config = _load_modbus_config(args.config)
    if args.port:
        config.port = args.port
    if args.baudrate is not None:
        config.baudrate = int(args.baudrate)
    if args.parity is not None:
        config.parity = str(args.parity)
    if args.slave is not None:
        config.slave_address = int(args.slave)
    if args.timeout is not None:
        config.timeout = float(args.timeout)

    repeat = max(1, int(args.repeat))
    hold = max(0.0, float(args.hold))
    delay = max(0.0, float(args.delay))
    all_ok = True
    blow_off_seconds = max(0.0, float(args.blow_off_seconds))
    print(
        f"Testing pump register {args.register}; "
        f"blow-off register {args.blow_off_register} for {blow_off_seconds:.3f}s "
        f"on {config.port} slave={config.slave_address} "
        f"{config.baudrate},{config.bytesize}{config.parity}{config.stopbits}"
    )

    controller = build_modbus_vacuum_pump_controller(
        modbus_config=config,
        vacuum_config=VacuumPumpConfig(
            pump_register=args.register,
            blow_off_register=args.blow_off_register,
            blow_off_pulse_seconds=blow_off_seconds,
        ),
    )
    readback_transport = _build_transport(config) if args.readback else None
    for index in range(repeat):
        if readback_transport is not None:
            _print_readback(readback_transport, "Before ON", args.register, args.blow_off_register)
        attempt_ok = controller.turn_on()
        all_ok = attempt_ok and all_ok
        print(f"ON command {index + 1}/{repeat}: {'ok' if attempt_ok else 'failed'}")
        if readback_transport is not None:
            _print_readback(readback_transport, "After ON", args.register, args.blow_off_register)
        print(f"Pump should be ON for {hold:.1f} seconds now")
        if hold > 0:
            time.sleep(hold)
        attempt_ok = controller.turn_off()
        all_ok = attempt_ok and all_ok
        print(f"OFF command {index + 1}/{repeat}: {'ok' if attempt_ok else 'failed'}")
        if readback_transport is not None:
            _print_readback(readback_transport, "After OFF", args.register, args.blow_off_register)
        if index + 1 < repeat and delay > 0:
            time.sleep(delay)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

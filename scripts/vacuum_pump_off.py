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
from src.engine.hardware.peripherals import PeripheralConfig, PeripheralConfigSerializer
from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig
from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_factory import (
    build_modbus_vacuum_pump_controller,
)
from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_transport import (
    ModbusVacuumPumpTransport,
)
from src.engine.hardware.xinje import XinjeMA8X8YR

DEFAULT_CONFIG = ROOT / "src" / "robot_systems" / "paint" / "storage" / "settings" / "hardware" / "modbus.json"
DEFAULT_PERIPHERALS_CONFIG = ROOT / "src" / "robot_systems" / "paint" / "storage" / "settings" / "hardware" / "peripherals.json"
DEFAULT_REGISTER = "Y0"
DEFAULT_BLOW_OFF_REGISTER = "Y1"
DEFAULT_BLOW_OFF_SECONDS = 0.2


def _load_modbus_config(path: Path) -> ModbusConfig:
    with path.open("r", encoding="utf-8") as fh:
        return ModbusConfig.from_dict(json.load(fh))


def _load_peripheral_config(path: Path) -> PeripheralConfig | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return PeripheralConfigSerializer().from_dict(json.load(fh))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _print_settings(
    args: argparse.Namespace,
    config: ModbusConfig,
    peripherals: PeripheralConfig | None,
) -> None:
    print("--- Effective vacuum pump test settings ---")
    print(f"modbus config: {args.config}")
    print(
        f"serial: port={config.port} baudrate={config.baudrate} "
        f"format={config.bytesize}{config.parity}{config.stopbits} timeout={config.timeout}s"
    )
    print(f"default slave: id={config.slave_address} retries={config.max_retries}")
    for name in config.slave_names():
        slave = config.get_slave(name)
        try:
            connection = config.get_connection(name)
            connection_text = (
                f"port={connection.port} baudrate={connection.baudrate} "
                f"format={connection.bytesize}{connection.parity}{connection.stopbits} "
                f"timeout={connection.timeout}s"
            )
        except Exception as exc:
            connection_text = f"connection_error={exc}"
        print(
            f"slave mapping: name={name} id={slave.slave_address} "
            f"profile={slave.profile_name} transport={slave.transport_type} "
            f"retries={slave.max_retries} {connection_text}"
        )
    if peripherals is not None:
        print(f"peripherals config: {DEFAULT_PERIPHERALS_CONFIG}")
        pump = peripherals.get("vacuum_pump")
        if pump is None:
            print("pump peripheral: disabled or not configured")
        else:
            print(
                f"pump peripheral: enabled slave_id={pump.slave_id} "
                f"pump={pump.outputs.get('pump', 'Y2')} "
                f"blow_off={pump.outputs.get('blow_off', 'disabled')}"
            )
    else:
        print(f"peripherals config: unavailable ({DEFAULT_PERIPHERALS_CONFIG})")
    print(
        f"command: mode={args.write_mode} register={_format_output_point(args.register)} "
        f"blow_off={_format_output_point(None if args.no_blow_off else args.blow_off_register)} "
        f"repeat={args.repeat} hold={args.hold}s readback={args.readback}"
    )
    print("--------------------------------------------")


def _parse_int(value: str) -> int:
    return int(value, 0)


def _parse_output_point(value: str) -> int | str:
    try:
        return _parse_int(value)
    except ValueError:
        return value


def _format_output_point(point: int | str | None) -> str:
    if point is None:
        return "disabled"
    resolved = XinjeMA8X8YR.resolve_output(point)
    return f"{point} ({resolved})" if point != resolved else str(resolved)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Turn the paint vacuum pump ON, wait, then turn it OFF.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=f"Modbus JSON path. Default: {DEFAULT_CONFIG}")
    parser.add_argument("--port", help="Override serial port from config, e.g. /dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, help="Override serial baudrate from config.")
    parser.add_argument("--parity", choices=("N", "E", "O"), help="Override serial parity from config.")
    parser.add_argument("--slave", type=int, help="Override Modbus slave address from config.")
    parser.add_argument("--timeout", type=float, help="Override serial timeout from config.")
    parser.add_argument("--register", type=_parse_output_point, default=DEFAULT_REGISTER, help=f"Vacuum pump coil/register address or Xinje output label. Default: {DEFAULT_REGISTER}")
    parser.add_argument("--blow-off-register", type=_parse_output_point, default=DEFAULT_BLOW_OFF_REGISTER, help=f"Blow-off coil/register address or Xinje output label. Default: {DEFAULT_BLOW_OFF_REGISTER}")
    parser.add_argument("--no-blow-off", action="store_true", help="Do not touch the blow-off relay; test only the pump relay.")
    parser.add_argument("--blow-off-seconds", type=float, default=DEFAULT_BLOW_OFF_SECONDS, help=f"How long to pulse blow-off after pump OFF. Default: {DEFAULT_BLOW_OFF_SECONDS}")
    parser.add_argument("--readback", action="store_true", help="Read pump and blow-off coils before and after each command when supported.")
    parser.add_argument("--force-off-after-failed-on", action="store_true", help="Send OFF even when ON failed.")
    parser.add_argument(
        "--write-mode",
        choices=("auto", "coil-fc5", "coil-bank16", "register-fc6", "register-bank16"),
        default="auto",
        help="Diagnostic write mode. Default: auto controller behavior.",
    )
    parser.add_argument(
        "--image-register",
        type=_parse_int,
        default=128,
        help="Base register/address for image write diagnostic modes. Default: 128.",
    )
    parser.add_argument("--repeat", type=int, default=1, help="How many ON/OFF pulses to send. Default: 1")
    parser.add_argument("--hold", type=float, default=30.0, help="How long to keep the pump ON before turning it OFF. Default: 5.0")
    parser.add_argument("--delay", type=float, default=0.05, help="Delay between pulses in seconds. Default: 0.05")
    return parser.parse_args()


def _build_transport(config: ModbusConfig) -> ModbusVacuumPumpTransport:
    return ModbusVacuumPumpTransport(
        port=config.port,
        slave_address=1,
        baudrate=config.baudrate,
        bytesize=config.bytesize,
        stopbits=config.stopbits,
        parity=config.parity,
        timeout=config.timeout,
    )


def _apply_connection(config: ModbusConfig, connection) -> None:
    config.port = connection.port
    config.baudrate = connection.baudrate
    config.bytesize = connection.bytesize
    config.stopbits = connection.stopbits
    config.parity = connection.parity
    config.timeout = connection.timeout
    config.slave_address = connection.slave_address
    config.max_retries = connection.max_retries


def _write_direct(
    transport: ModbusVacuumPumpTransport,
    mode: str,
    address: int | str,
    image_register: int,
    value: int,
) -> None:
    address = XinjeMA8X8YR.resolve_output(address)
    bit_index = max(0, address - image_register)
    image_value = 1 << bit_index if value else 0

    if mode == "coil-fc5":
        transport.write_coil_fc5(address, bool(value))
    elif mode == "coil-bank16":
        values = [0] * 16
        if 0 <= bit_index < len(values):
            values[bit_index] = 1 if value else 0
        transport.write_coils_fc15(image_register, values)
    elif mode == "register-fc6":
        transport.write_register_fc6(image_register, image_value)
    elif mode == "register-bank16":
        values = [0] * 16
        if 0 <= bit_index < len(values):
            values[bit_index] = 1 if value else 0
        transport.write_registers_fc16(image_register, values)
    else:
        raise ValueError(f"Unsupported write mode: {mode}")


def _run_direct_mode(args: argparse.Namespace, config: ModbusConfig) -> int:
    transport = _build_transport(config)
    repeat = max(1, int(args.repeat))
    hold = max(0.0, float(args.hold))
    delay = max(0.0, float(args.delay))
    all_ok = True

    print(
        f"Testing direct {args.write_mode}: output register {_format_output_point(args.register)}, "
        f"image register {args.image_register} on {config.port} "
        f"slave={config.slave_address} {config.baudrate},"
        f"{config.bytesize}{config.parity}{config.stopbits}"
    )

    for index in range(repeat):
        try:
            _write_direct(transport, args.write_mode, args.register, args.image_register, 1)
            print(f"ON command {index + 1}/{repeat}: ok")
            if hold > 0:
                time.sleep(hold)
            _write_direct(transport, args.write_mode, args.register, args.image_register, 0)
            print(f"OFF command {index + 1}/{repeat}: ok")
        except Exception as exc:
            all_ok = False
            print(f"Direct test {index + 1}/{repeat}: failed ({exc})")

        if index + 1 < repeat and delay > 0:
            time.sleep(delay)

    return 0 if all_ok else 1


def _print_readback(
    transport: ModbusVacuumPumpTransport,
    label: str,
    pump_register: int | str,
    blow_off_register: int | str | None,
) -> None:
    pump_register = XinjeMA8X8YR.resolve_output(pump_register)
    blow_off_address = (
        XinjeMA8X8YR.resolve_output(blow_off_register)
        if blow_off_register is not None
        else None
    )
    try:
        pump = transport.read_register(pump_register)
        blow_off = (
            transport.read_register(blow_off_address)
            if blow_off_address is not None
            else None
        )
    except Exception as exc:
        print(f"{label} readback failed: {exc}")
        return
    if blow_off is None:
        print(f"{label} readback: pump={pump}")
    else:
        print(f"{label} readback: pump={pump} blow_off={blow_off}")


def main() -> int:
    args = _parse_args()
    config = _load_modbus_config(args.config)
    peripherals = _load_peripheral_config(DEFAULT_PERIPHERALS_CONFIG)
    pump_slave_name = "default"
    pump = peripherals.get("vacuum_pump") if peripherals is not None else None
    if pump is not None:
        pump_slave_name = config.find_slave_name(pump.slave_id)
        _apply_connection(config, config.get_connection(pump_slave_name))
        if args.register == DEFAULT_REGISTER:
            args.register = pump.outputs.get("pump", DEFAULT_REGISTER)
        if args.blow_off_register == DEFAULT_BLOW_OFF_REGISTER:
            args.blow_off_register = pump.outputs.get("blow_off", DEFAULT_BLOW_OFF_REGISTER)
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

    _print_settings(args, config, peripherals)

    if args.write_mode != "auto":
        return _run_direct_mode(args, config)

    repeat = max(1, int(args.repeat))
    hold = max(0.0, float(args.hold))
    delay = max(0.0, float(args.delay))
    all_ok = True
    blow_off_seconds = max(0.0, float(args.blow_off_seconds))
    blow_off_register = None if args.no_blow_off else args.blow_off_register
    print(
        f"Testing pump register {_format_output_point(args.register)}; "
        f"blow-off register {_format_output_point(blow_off_register)} "
        f"for {blow_off_seconds:.3f}s "
        f"on {config.port} slave={config.slave_address} "
        f"{config.baudrate},{config.bytesize}{config.parity}{config.stopbits}"
    )

    controller = build_modbus_vacuum_pump_controller(
        modbus_config=config,
        profile_name=pump_slave_name,
        vacuum_config=VacuumPumpConfig(
            pump_register=args.register,
            blow_off_register=blow_off_register,
            blow_off_pulse_seconds=blow_off_seconds,
        ),
    )
    readback_transport = _build_transport(config) if args.readback else None
    for index in range(repeat):
        if readback_transport is not None:
            _print_readback(readback_transport, "Before ON", args.register, blow_off_register)
        attempt_ok = controller.turn_on()
        all_ok = attempt_ok and all_ok
        print(f"ON command {index + 1}/{repeat}: {'ok' if attempt_ok else 'failed'}")
        if readback_transport is not None:
            _print_readback(readback_transport, "After ON", args.register, blow_off_register)
        if attempt_ok:
            print(f"Pump should be ON for {hold:.1f} seconds now")
        else:
            print("Pump ON failed; skipping hold")
        if attempt_ok and hold > 0:
            time.sleep(hold)
        if not attempt_ok and not args.force_off_after_failed_on:
            print("Skipping OFF because ON did not succeed")
            continue
        attempt_ok = controller.turn_off()
        all_ok = attempt_ok and all_ok
        print(f"OFF command {index + 1}/{repeat}: {'ok' if attempt_ok else 'failed'}")
        if readback_transport is not None:
            _print_readback(readback_transport, "After OFF", args.register, blow_off_register)
        if index + 1 < repeat and delay > 0:
            time.sleep(delay)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

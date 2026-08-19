"""Interactive manual test runner for Paint peripheral configuration.

Run from the repository root:
    .venv/bin/python scripts/test_paint_peripherals.py

No actuator is changed until an explicit ``on``, ``off``, or ``pulse`` command
is entered.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY
from src.engine.hardware.fan.modbus.modbus_fan_control import ModbusFanControl
from src.engine.hardware.laser import ModbusLaserControl
from src.engine.hardware.peripherals import PeripheralConfig, PeripheralConfigSerializer
from src.engine.hardware.physical_control_buttons.modbus.modbus_physical_control_buttons_factory import (
    build_modbus_physical_control_buttons,
)
from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig
from src.engine.hardware.vacuum_pump.vacuum_pump_controller import VacuumPumpController
from src.engine.hardware.vacuum_sensor.models.vacuum_sensor_config import VacuumSensorConfig
from src.engine.hardware.vacuum_sensor.vacuum_sensor_service import VacuumSensorService
from src.engine.hardware.xinje import XinjeMA8X8YR


SETTINGS_DIR = ROOT / "src" / "robot_systems" / "paint" / "storage" / "settings" / "hardware"
MODBUS_PATH = SETTINGS_DIR / "modbus.json"
PERIPHERALS_PATH = SETTINGS_DIR / "peripherals.json"


def load_configuration() -> tuple[ModbusConfig, PeripheralConfig]:
    with MODBUS_PATH.open("r", encoding="utf-8") as stream:
        modbus = ModbusConfig.from_dict(json.load(stream))
    with PERIPHERALS_PATH.open("r", encoding="utf-8") as stream:
        peripherals = PeripheralConfigSerializer().from_dict(json.load(stream))
    return modbus, peripherals


def transport_for(modbus: ModbusConfig, slave_id: int):
    slave_name = modbus.find_slave_name(slave_id)
    return DEFAULT_TRANSPORT_REGISTRY.build_for_slave(modbus, slave_name)


def build_devices(modbus: ModbusConfig, peripherals: PeripheralConfig) -> dict[str, object]:
    devices: dict[str, object] = {}

    pump = peripherals.get("vacuum_pump")
    if pump is not None:
        devices["vacuum_pump"] = VacuumPumpController(
            transport=transport_for(modbus, pump.slave_id),
            config=VacuumPumpConfig(
                pump_register=pump.outputs.get("pump", "Y2"),
                blow_off_register=pump.outputs.get("blow_off"),
                blow_off_pulse_seconds=0.2,
            ),
        )

    fan = peripherals.get("fan")
    if fan is not None:
        devices["fan"] = ModbusFanControl(
            transport=transport_for(modbus, fan.slave_id),
            register=fan.outputs.get("fan", "Y0"),
        )

    laser = peripherals.get("laser")
    if laser is not None:
        devices["laser"] = ModbusLaserControl(
            transport=transport_for(modbus, laser.slave_id),
            register=laser.outputs.get("enable", "Y5"),
        )

    buttons = peripherals.get("physical_control_buttons")
    if buttons is not None:
        button_device = build_modbus_physical_control_buttons(modbus, peripherals)
        if button_device is not None:
            devices["physical_control_buttons"] = button_device

    sensor = peripherals.get("vacuum_sensor")
    if sensor is not None:
        devices["vacuum_sensor"] = VacuumSensorService(
            transport=transport_for(modbus, sensor.slave_id),
            config=VacuumSensorConfig(
                sensor_register=(
                    sensor.inputs.get("sensor")
                    or sensor.outputs.get("sensor", "Y4")
                ),
                detected_value=1,
                read_retries=3,
            ),
        )

    return devices


def read_sensor(device: VacuumSensorService) -> None:
    detected = device.is_vacuum_detected()
    print(f"vacuum_sensor: detected={detected} healthy={device.is_healthy()}")


def read_device(device: object, name: str, duration_s: float) -> None:
    """Read a device once or poll it for the requested duration."""
    deadline = time.monotonic() + max(0.0, duration_s)
    while True:
        if name == "physical_control_buttons":
            value = {
                "inputs": dict(device.read_states()),
                "outputs": dict(device.read_output_states()),
            }
        elif name == "vacuum_sensor":
            value = {
                "detected": device.is_vacuum_detected(),
                "healthy": device.is_healthy(),
            }
        else:
            print("Read is supported for physical_control_buttons and vacuum_sensor.")
            return
        print(f"{name}: {value}")
        if time.monotonic() >= deadline:
            return
        time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))


def print_help() -> None:
    print("Commands:")
    print("  list                         list configured peripherals")
    print("  read <device> [seconds]      read once or poll for seconds")
    print("  on <pump|fan|laser> [s]      turn on, then off after s")
    print("  off <pump|fan|laser>         turn an output off")
    print("  on physical_control_buttons <button> [s]")
    print("  off physical_control_buttons <button>")
    print("  pulse <pump|fan|laser> [s]   turn on, wait, then turn off")
    print("  help                         show this help")
    print("  quit                         exit")


def main() -> None:
    modbus, peripherals = load_configuration()
    devices = build_devices(modbus, peripherals)
    print(f"Loaded {MODBUS_PATH}")
    print(f"Loaded {PERIPHERALS_PATH}")
    print(f"Configured transports: {DEFAULT_TRANSPORT_REGISTRY.keys()}")
    print(f"Devices: {', '.join(devices) or 'none'}")
    print_help()

    while True:
        try:
            command = input("peripherals> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not command:
            continue
        parts = command.split()
        action = parts[0].lower()
        if action in {"quit", "exit", "q"}:
            return
        if action == "help":
            print_help()
            continue
        if action == "list":
            for name in devices:
                print(f"  {name}")
            continue
        if len(parts) < 2:
            print("Expected a device name. Use 'help'.")
            continue

        name = parts[1].lower()
        device = devices.get(name)
        if device is None:
            print(f"Unknown or disabled device: {name}")
            continue
        try:
            if action == "read" and name == "physical_control_buttons":
                duration_s = float(parts[2]) if len(parts) > 2 else 0.0
                read_device(device, name, duration_s)
            elif action == "read" and name == "vacuum_sensor":
                duration_s = float(parts[2]) if len(parts) > 2 else 0.0
                read_device(device, name, duration_s)
            elif name == "physical_control_buttons" and action in {"on", "off"}:
                if len(parts) < 3:
                    print("Specify a button, for example: on physical_control_buttons start")
                    continue
                hold_s = float(parts[3]) if action == "on" and len(parts) > 3 else 0.0
                device.set_button(parts[2], action == "on")
                try:
                    output_states = device.read_output_states()
                    print(
                        f"{name} {parts[2]}={action == 'on'} sent; "
                        f"output readback={output_states.get(parts[2], 'unavailable')}"
                    )
                    if hold_s > 0:
                        time.sleep(hold_s)
                finally:
                    if action == "on" and hold_s > 0:
                        device.set_button(parts[2], False)
                        print(f"{name} {parts[2]}=False sent after {hold_s:.3f}s")
            elif action == "on" and hasattr(device, "turn_on"):
                hold_s = float(parts[2]) if len(parts) > 2 else 0.0
                result = device.turn_on()
                try:
                    print(f"{name} ON: {result}" if result is not None else f"{name} ON sent")
                    if hold_s > 0:
                        print(f"{name} holding ON for {hold_s:.3f}s")
                        time.sleep(hold_s)
                finally:
                    if hold_s > 0:
                        device.turn_off()
                        print(f"{name} OFF sent after {hold_s:.3f}s")
            elif action == "off" and hasattr(device, "turn_off"):
                result = device.turn_off()
                print(f"{name} OFF: {result}" if result is not None else f"{name} OFF sent")
            elif action == "pulse" and hasattr(device, "turn_on") and hasattr(device, "turn_off"):
                hold_s = float(parts[2]) if len(parts) > 2 else 1.0
                device.turn_on()
                time.sleep(max(0.0, hold_s))
                device.turn_off()
                print(f"{name} pulsed for {hold_s:.3f}s")
            else:
                print("Unsupported command for this device. Use 'help'.")
        except Exception as exc:
            print(f"{name} {action} failed: {exc}")


if __name__ == "__main__":
    main()

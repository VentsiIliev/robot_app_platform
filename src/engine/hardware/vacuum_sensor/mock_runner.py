from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY
from src.engine.hardware.peripherals import PeripheralConfig, PeripheralConfigSerializer
from src.engine.hardware.vacuum_sensor.models.vacuum_sensor_config import VacuumSensorConfig
from src.engine.hardware.vacuum_sensor.vacuum_sensor_service import VacuumSensorService
from src.engine.hardware.xinje import XinjeMA8X8YR

ROOT = Path(__file__).resolve().parents[4]
MODBUS_CONFIG_PATH = ROOT / "src" / "robot_systems" / "paint" / "storage" / "settings" / "hardware" / "modbus.json"
PERIPHERALS_CONFIG_PATH = ROOT / "src" / "robot_systems" / "paint" / "storage" / "settings" / "hardware" / "peripherals.json"
DETECTED_VALUE = 1
READ_RETRIES = 3
READ_COUNT = 100000
READ_DELAY_S = 0.5


def _load_modbus_config(path: Path) -> ModbusConfig:
    with path.open("r", encoding="utf-8") as fh:
        return ModbusConfig.from_dict(json.load(fh))


def _load_peripherals(path: Path) -> PeripheralConfig:
    with path.open("r", encoding="utf-8") as fh:
        return PeripheralConfigSerializer().from_dict(json.load(fh))


def _build_transport(config: ModbusConfig, slave_id: int):
    slave_name = config.find_slave_name(slave_id)
    return slave_name, DEFAULT_TRANSPORT_REGISTRY.build_for_slave(config, slave_name)


def run_real_sensor() -> None:
    modbus_config = _load_modbus_config(MODBUS_CONFIG_PATH)
    peripherals = _load_peripherals(PERIPHERALS_CONFIG_PATH)
    sensor = peripherals.get("vacuum_sensor")
    if sensor is None:
        raise RuntimeError(
            f"vacuum_sensor is missing or disabled in {PERIPHERALS_CONFIG_PATH}"
        )

    sensor_point = sensor.inputs.get("sensor") or sensor.outputs.get("sensor")
    if sensor_point is None:
        raise RuntimeError(
            f"vacuum_sensor has no inputs.sensor/output.sensor in {PERIPHERALS_CONFIG_PATH}"
        )

    slave_name, transport = _build_transport(modbus_config, sensor.slave_id)
    address = (
        XinjeMA8X8YR.resolve_input(sensor_point)
        if sensor_point.upper().startswith("X")
        else XinjeMA8X8YR.resolve_output(sensor_point)
    )
    connection = modbus_config.get_connection(slave_name)
    print(
        f"Reading vacuum sensor {sensor_point} ({address}) from {connection.port} "
        f"slave={connection.slave_address} {connection.baudrate},"
        f"{connection.bytesize}{connection.parity}{connection.stopbits} "
        f"profile={slave_name} transport={modbus_config.get_slave(slave_name).transport_type}"
    )

    service = VacuumSensorService(
        transport=transport,
        config=VacuumSensorConfig(
            sensor_register=sensor_point,
            detected_value=DETECTED_VALUE,
            read_retries=READ_RETRIES,
        ),
    )

    for index in range(READ_COUNT):
        detected = service.is_vacuum_detected()
        print(
            f"read {index + 1}/{READ_COUNT}: "
            f"detected={detected} healthy={service.is_healthy()}"
        )
        if index + 1 < READ_COUNT and READ_DELAY_S > 0:
            time.sleep(READ_DELAY_S)


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run_real_sensor()

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

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
DETECTED_VALUE = 0
READ_RETRIES = 3
READ_COUNT = 100000
READ_DELAY_S = 0.5


def _build_sensor() -> tuple[VacuumSensorService, object, str, int, object]:
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
    connection = modbus_config.get_connection(slave_name)
    address = (
        XinjeMA8X8YR.resolve_input(sensor_point)
        if sensor_point.upper().startswith("X")
        else XinjeMA8X8YR.resolve_output(sensor_point)
    )
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
    return service, transport, sensor_point, address, connection


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
    service, transport, _sensor_point, _address, _connection = _build_sensor()

    for index in range(READ_COUNT):
        detected = service.is_vacuum_detected()
        print(
            f"read {index + 1}/{READ_COUNT}: "
            f"raw={service.last_raw_value} detected={detected} "
            f"healthy={service.is_healthy()}"
        )
        if index + 1 < READ_COUNT and READ_DELAY_S > 0:
            time.sleep(READ_DELAY_S)


class SensorMonitorWindow(QWidget):
    def __init__(self, service: VacuumSensorService, transport: object) -> None:
        super().__init__()
        self._service = service
        self._transport = transport
        self._read_count = 0
        self.setWindowTitle("Vacuum Sensor Monitor")
        self.resize(420, 280)

        self._indicator = QLabel("UNKNOWN")
        self._indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._indicator.setMinimumHeight(120)
        self._raw = QLabel("Raw value: -")
        self._health = QLabel("Communication: -")
        self._count = QLabel("Reads: 0")

        layout = QVBoxLayout(self)
        layout.addWidget(self._indicator)
        layout.addWidget(self._raw)
        layout.addWidget(self._health)
        layout.addWidget(self._count)
        self._set_indicator(None)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._read_sensor)
        self._timer.start(int(READ_DELAY_S * 1000))
        self._read_sensor()

    def _read_sensor(self) -> None:
        detected = self._service.is_vacuum_detected()
        healthy = self._service.is_healthy()
        self._read_count += 1
        self._set_indicator(detected if healthy else None)
        self._raw.setText(f"Raw value: {self._service.last_raw_value}")
        self._health.setText(f"Communication: {'OK' if healthy else 'FAILED'}")
        self._count.setText(f"Reads: {self._read_count}")

    def _set_indicator(self, detected: bool | None) -> None:
        if detected is True:
            text, color = "VACUUM DETECTED", "#2E7D32"
        elif detected is False:
            text, color = "NO VACUUM", "#C62828"
        else:
            text, color = "COMMUNICATION ERROR", "#757575"
        self._indicator.setText(text)
        self._indicator.setStyleSheet(
            f"background-color: {color}; color: white; "
            "font-size: 24px; font-weight: bold; border-radius: 8px; padding: 20px;"
        )

    def closeEvent(self, event) -> None:
        self._timer.stop()
        self._transport.disconnect()
        super().closeEvent(event)


def run_gui() -> None:
    service, transport, _sensor_point, _address, _connection = _build_sensor()
    app = QApplication(sys.argv)
    window = SensorMonitorWindow(service, transport)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run_gui()

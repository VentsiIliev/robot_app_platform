from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from PyQt6.QtWidgets import QApplication, QMainWindow

from src.applications.dryer_settings.dryer_settings_factory import DryerSettingsFactory
from src.applications.dryer_settings.service.stub_dryer_settings_service import StubDryerSettingsService
from src.engine.hardware.communication.modbus.modbus import ModbusConfig


def run_standalone() -> None:
    modbus_config = ModbusConfig(
        port="/dev/ttyUSB0",
        baudrate=115200,
        bytesize=8,
        stopbits=1,
        parity="N",
        timeout=0.3,
        slave_address=10,
        max_retries=3,
    )

    app = QApplication(sys.argv)
    service = StubDryerSettingsService(modbus_config=modbus_config)
    widget = DryerSettingsFactory().build(service)

    window = QMainWindow()
    window.setWindowTitle("Dryer Settings")
    window.setCentralWidget(widget)
    window.resize(1280, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()

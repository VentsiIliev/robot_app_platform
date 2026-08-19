from __future__ import annotations

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.dryer.dryer_controller import DryerController
from src.engine.hardware.dryer.interfaces.i_dryer_controller import IDryerController
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.modbus.modbus_dryer_transport import ModbusDryerTransport


def build_modbus_dryer_controller(
    modbus_config: ModbusConfig,
    dryer_config: DryerConfig | None = None,
) -> IDryerController:
    transport = ModbusDryerTransport(
        port=modbus_config.port,
        slave_address=modbus_config.slave_address,
        baudrate=modbus_config.baudrate,
        bytesize=modbus_config.bytesize,
        stopbits=modbus_config.stopbits,
        parity=modbus_config.parity,
        timeout=modbus_config.timeout,
    )
    return DryerController(
        transport=transport,
        config=dryer_config or DryerConfig(),
    )

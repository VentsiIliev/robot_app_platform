from __future__ import annotations

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY
from src.engine.hardware.dryer.interfaces.i_dryer_controller import IDryerController
from src.engine.hardware.dryer.modbus.modbus_plate_dryer_controller import (
    ModbusPlateDryerController,
)


def build_modbus_plate_dryer_controller(
    modbus_config: ModbusConfig,
    slave_name: str,
    plate_register: int = 2,
    open_value: int = 2,
    close_value: int = 0,
) -> IDryerController:
    transport = DEFAULT_TRANSPORT_REGISTRY.build_for_slave(modbus_config, slave_name)
    return ModbusPlateDryerController(
        transport=transport,
        plate_register=plate_register,
        open_value=open_value,
        close_value=close_value,
    )

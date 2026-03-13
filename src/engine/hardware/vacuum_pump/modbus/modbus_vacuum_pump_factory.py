from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig
from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_transport import ModbusVacuumPumpTransport
from src.engine.hardware.vacuum_pump.vacuum_pump_controller import VacuumPumpController


def build_modbus_vacuum_pump_controller(
    modbus_config,
    pump_config: VacuumPumpConfig = None,
) -> IVacuumPumpController:
    transport = ModbusVacuumPumpTransport(
        port          = modbus_config.port,
        slave_address = modbus_config.slave_address,
        baudrate      = modbus_config.baudrate,
        bytesize      = modbus_config.bytesize,
        stopbits      = modbus_config.stopbits,
        parity        = modbus_config.parity,
        timeout       = modbus_config.timeout,
    )
    return VacuumPumpController(transport=transport, config=pump_config)

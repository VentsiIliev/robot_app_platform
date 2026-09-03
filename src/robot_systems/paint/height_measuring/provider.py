from __future__ import annotations

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.hardware.laser import ModbusLaserControl
from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.peripherals import PeripheralConfig
from src.robot_systems.paint.component_ids import SettingsID
from src.engine.robot.height_measuring import RobotSystemHeightMeasuringProvider


class PaintRobotSystemHeightMeasuringProvider(RobotSystemHeightMeasuringProvider):

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_laser_control(self):
        modbus_config = self._robot_system._settings_service.get(CommonSettingsID.MODBUS_CONFIG)
        peripheral_config = None
        if isinstance(modbus_config, ModbusConfig):
            peripheral_config = self._robot_system._settings_service.get(SettingsID.PERIPHERALS)
        binding = (
            peripheral_config.get("laser")
            if isinstance(peripheral_config, PeripheralConfig)
            else None
        )
        slave_name = "xinje_ma"
        register = "Y5"
        on_value = 1
        off_value = 0
        if binding is not None:
            try:
                slave_name = modbus_config.find_slave_name(binding.slave_id)
            except KeyError as exc:
                raise RuntimeError(
                    f"Laser peripheral requires Modbus slave {binding.slave_id}, "
                    "but that slave is not configured in Modbus settings"
                ) from exc
            register = binding.outputs.get("enable", register)
            on_value = binding.commands.get("on", on_value)
            off_value = binding.commands.get("off", off_value)
        if hasattr(modbus_config, "get_connection"):
            transport = DEFAULT_TRANSPORT_REGISTRY.build_for_slave(modbus_config, slave_name)
        else:
            from src.engine.hardware.communication.modbus.modbus_register_transport import ModbusRegisterTransport
            transport = ModbusRegisterTransport(
                port=modbus_config.port,
                slave_address=modbus_config.slave_address,
                baudrate=modbus_config.baudrate,
                bytesize=modbus_config.bytesize,
                stopbits=modbus_config.stopbits,
                parity=modbus_config.parity,
                timeout=modbus_config.timeout,
            )
        return ModbusLaserControl(
            transport=transport,
            register=register,
            on_value=on_value,
            off_value=off_value,
        )

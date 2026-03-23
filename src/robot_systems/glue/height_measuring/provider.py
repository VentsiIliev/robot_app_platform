from __future__ import annotations

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.hardware.communication import LiveRegisterTransport
from src.engine.hardware.communication.modbus.modbus_register_transport import ModbusRegisterTransport
from src.engine.robot.height_measuring.robot_system_height_measuring_provider import (
    RobotSystemHeightMeasuringProvider,
)
from src.robot_systems.glue.tools.glue_laser_control import GlueLaserControl


class GlueRobotSystemHeightMeasuringProvider(RobotSystemHeightMeasuringProvider):
    """Glue adapter that supplies the laser-control implementation."""

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_laser_control(self):
        return GlueLaserControl(LiveRegisterTransport(self._build_transport))

    def _build_transport(self):
        cfg = self._robot_system.get_settings(CommonSettingsID.MODBUS_CONFIG)
        return ModbusRegisterTransport(
            port=cfg.port,
            slave_address=cfg.slave_address,
            baudrate=cfg.baudrate,
            bytesize=cfg.bytesize,
            stopbits=cfg.stopbits,
            parity=cfg.parity,
            timeout=cfg.timeout,
        )

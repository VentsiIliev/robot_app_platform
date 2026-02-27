from __future__ import annotations
from typing import Callable, Optional

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.generator.generator_controller import GeneratorController
from src.engine.hardware.generator.interfaces.i_generator_controller import IGeneratorController
from src.engine.hardware.generator.models.generator_config import GeneratorConfig
from src.engine.hardware.generator.modbus.modbus_generator_transport import ModbusGeneratorTransport
from src.engine.hardware.generator.timer.generator_timer import GeneratorTimer, NullGeneratorTimer
from src.engine.hardware.generator.timer.i_generator_timer import IGeneratorTimer


def build_modbus_generator_controller(
    modbus_config:    ModbusConfig,
    generator_config: GeneratorConfig              = None,
    on_timeout:       Optional[Callable[[], None]] = None,
) -> IGeneratorController:
    transport = ModbusGeneratorTransport(
        port          = modbus_config.port,
        slave_address = modbus_config.slave_address,
        baudrate      = modbus_config.baudrate,
        bytesize      = modbus_config.bytesize,
        stopbits      = modbus_config.stopbits,
        parity        = modbus_config.parity,
        timeout       = modbus_config.timeout,
    )
    cfg: GeneratorConfig = generator_config or GeneratorConfig()
    timer: IGeneratorTimer = (
        GeneratorTimer(timeout_minutes=cfg.timeout_minutes, on_timeout=on_timeout)
        if on_timeout is not None else NullGeneratorTimer()
    )
    return GeneratorController(transport=transport, config=cfg, timer=timer)
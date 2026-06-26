from __future__ import annotations

import logging

from src.engine.common_settings_ids import CommonSettingsID

_logger = logging.getLogger(__name__)


def build_vacuum_pump_service(ctx):
    from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig
    from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_factory import (
        build_modbus_vacuum_pump_controller,
    )

    try:
        modbus_config = ctx.settings.get(CommonSettingsID.MODBUS_CONFIG)
        return build_modbus_vacuum_pump_controller(
            modbus_config=modbus_config,
            vacuum_config=VacuumPumpConfig(pump_register=128),
        )
    except Exception:
        _logger.exception("Vacuum pump service could not be built; continuing without it")
        return None

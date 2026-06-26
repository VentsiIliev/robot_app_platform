from __future__ import annotations

import logging
import time

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_transport import IVacuumPumpTransport
from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig

_logger = logging.getLogger(__name__)


class VacuumPumpController(IVacuumPumpController):
    def __init__(
        self,
        transport: IVacuumPumpTransport,
        config: VacuumPumpConfig | None = None,
    ) -> None:
        self._transport = transport
        self._config = config or VacuumPumpConfig()

    def turn_on(self) -> bool:
        return self._write_pump(self._config.on_value, "ON")

    def turn_off(self) -> bool:
        if not self._write_pump(self._config.off_value, "OFF"):
            return False
        return self._pulse_blow_off()

    def _write_pump(self, value: int, label: str) -> bool:
        try:
            self._transport.write_register(self._config.pump_register, int(value))
        except Exception:
            _logger.exception(
                "Vacuum pump %s failed register=%d value=%d",
                label,
                self._config.pump_register,
                value,
            )
            return False
        _logger.info(
            "Vacuum pump %s register=%d value=%d",
            label,
            self._config.pump_register,
            value,
        )
        return True

    def _pulse_blow_off(self) -> bool:
        register = self._config.blow_off_register
        if register is None:
            return True
        try:
            self._transport.write_register(register, int(self._config.blow_off_on_value))
            if self._config.blow_off_pulse_seconds > 0:
                time.sleep(self._config.blow_off_pulse_seconds)
            self._transport.write_register(register, int(self._config.blow_off_off_value))
        except Exception:
            _logger.exception("Vacuum pump blow-off pulse failed register=%d", register)
            return False
        return True

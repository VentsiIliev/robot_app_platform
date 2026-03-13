from __future__ import annotations
import logging
import time

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_transport import IVacuumPumpTransport
from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig


class VacuumPumpController(IVacuumPumpController):

    def __init__(
        self,
        transport: IVacuumPumpTransport,
        config:    VacuumPumpConfig = None,
    ) -> None:
        self._transport = transport
        self._config    = config or VacuumPumpConfig()
        self._logger    = logging.getLogger(self.__class__.__name__)

    def turn_on(self) -> bool:
        self._logger.info("turn_on →")
        try:
            self._transport.write_register(self._config.pump_register, self._config.on_value)
            self._logger.info("turn_on ← ok")
            return True
        except Exception:
            self._logger.exception("turn_on failed")
            return False

    def turn_off(self) -> bool:
        self._logger.info("turn_off →")
        try:
            self._transport.write_register(self._config.pump_register, self._config.off_value)
            self._pulse_blow_off()
            self._logger.info("turn_off ← ok")
            return True
        except Exception:
            self._logger.exception("turn_off failed")
            return False

    def _pulse_blow_off(self) -> None:
        cfg = self._config
        if cfg.blow_off_register is None:
            return
        try:
            self._transport.write_register(cfg.blow_off_register, cfg.blow_off_on_value)
            time.sleep(cfg.blow_off_pulse_seconds)
            self._transport.write_register(cfg.blow_off_register, cfg.blow_off_off_value)
        except Exception:
            self._logger.exception("blow-off pulse failed")


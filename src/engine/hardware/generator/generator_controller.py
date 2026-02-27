from __future__ import annotations
import logging

from src.engine.hardware.generator.interfaces.i_generator_controller import IGeneratorController
from src.engine.hardware.generator.interfaces.i_generator_transport import IGeneratorTransport
from src.engine.hardware.generator.models.generator_config import GeneratorConfig
from src.engine.hardware.generator.models.generator_state import GeneratorState
from src.engine.hardware.generator.timer.generator_timer import NullGeneratorTimer
from src.engine.hardware.generator.timer.i_generator_timer import IGeneratorTimer


class GeneratorController(IGeneratorController):

    def __init__(
        self,
        transport: IGeneratorTransport,
        config:    GeneratorConfig = None,
        timer:     IGeneratorTimer = None,
    ) -> None:
        self._transport = transport
        self._config    = config or GeneratorConfig()
        self._timer     = timer  or NullGeneratorTimer()
        self._logger    = logging.getLogger(self.__class__.__name__)

    def turn_on(self) -> bool:
        self._logger.info("turn_on →")
        try:
            self._transport.write_register(self._config.relay_register, 1)
            self._timer.start()
            self._logger.info("turn_on ← ok")
            return True
        except Exception:
            self._logger.exception("turn_on failed")
            return False

    def turn_off(self) -> bool:
        self._logger.info("turn_off →")
        try:
            self._transport.write_register(self._config.relay_register, 0)
            self._timer.stop()
            self._logger.info("turn_off ← ok")
            return True
        except Exception:
            self._logger.exception("turn_off failed")
            return False

    def get_state(self) -> GeneratorState:
        try:
            raw   = self._transport.read_register(self._config.state_register)
            is_on = (raw == 0)   # hardware convention: 0 = ON, 1 = OFF
            return GeneratorState(
                is_on           = is_on,
                is_healthy      = True,
                elapsed_seconds = self._timer.elapsed_seconds,
            )
        except Exception as exc:
            self._logger.exception("get_state failed")
            return GeneratorState(
                is_on                = False,
                is_healthy           = False,
                communication_errors = [str(exc)],
                elapsed_seconds      = self._timer.elapsed_seconds,
            )
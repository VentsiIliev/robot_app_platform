from __future__ import annotations
import logging
import time
from typing import List, Optional

from src.engine.hardware.motor.health.motor_health_checker import MotorHealthChecker
from src.engine.hardware.motor.interfaces.i_motor_error_decoder import IMotorErrorDecoder
from src.engine.hardware.motor.interfaces.i_motor_service import IMotorService
from src.engine.hardware.motor.interfaces.i_motor_transport import IMotorTransport
from src.engine.hardware.motor.models.motor_config import MotorConfig
from src.engine.hardware.motor.models.motor_state import MotorState, MotorsSnapshot
from src.engine.hardware.motor.utils import split_into_16bit


class MotorService(IMotorService):
    """
    IMotorService implementation — uses IMotorTransport for all I/O.
    Has no knowledge of Modbus, serial ports, or any communication protocol.
    """

    def __init__(
        self,
        transport:     IMotorTransport,
        config:        MotorConfig,
        error_decoder: Optional[IMotorErrorDecoder] = None,
    ) -> None:
        self._transport  = transport
        self._config     = config
        self._health     = MotorHealthChecker(self._transport, self._config, error_decoder)
        self._logger     = logging.getLogger(self.__class__.__name__)
        self._connected  = False

    # ── IHealthCheckable ──────────────────────────────────────────────

    def is_healthy(self) -> bool:
        """Returns True when the service has an open connection and is ready for commands."""
        return self._connected

    # ── Motor topology ────────────────────────────────────────────────

    @property
    def motor_addresses(self) -> List[int]:
        """The motor addresses declared in this service's MotorConfig."""
        return self._config.motor_addresses

    # ── IMotorService — lifecycle ─────────────────────────────────────

    def open(self) -> None:
        try:
            self._transport.connect()
            self._connected = True
            self._logger.info("Motor service connected")
        except Exception:
            self._connected = False
            self._logger.exception("Motor service failed to connect — running disconnected")

    def close(self) -> None:
        try:
            self._transport.disconnect()
        except Exception:
            self._logger.warning("Motor service disconnect raised an error", exc_info=True)
        finally:
            self._connected = False

    # ── IMotorService — commands ──────────────────────────────────────

    def turn_on(
        self,
        motor_address:               int,
        speed:                       int,
        ramp_steps:                  int,
        initial_ramp_speed:          int,
        initial_ramp_speed_duration: float,
    ) -> bool:
        self._logger.info(
            "turn_on motor=%s speed=%s ramp_steps=%s initial_speed=%s initial_dur=%.2fs",
            motor_address, speed, ramp_steps, initial_ramp_speed, initial_ramp_speed_duration,
        )
        try:
            if not self._ramp(motor_address, initial_ramp_speed, ramp_steps):
                return False
            time.sleep(initial_ramp_speed_duration)
            high, low = split_into_16bit(speed)
            self._transport.write_registers(motor_address, [low, high])
            self._logger.info("Motor %s running at speed %s", motor_address, speed)
            return True
        except Exception:
            self._logger.exception("turn_on failed for motor %s", motor_address)
            return False

    def turn_off(
        self,
        motor_address:    int,
        speed_reverse:    int,
        reverse_duration: float,
        ramp_steps:       int,
    ) -> bool:
        self._logger.info(
            "turn_off motor=%s reverse_speed=%s duration=%.2fs",
            motor_address, speed_reverse, reverse_duration,
        )
        try:
            self._transport.write_registers(motor_address, [0, 0])
            if not self._ramp(motor_address, -abs(speed_reverse), ramp_steps):
                return False
            time.sleep(reverse_duration)
            self._transport.write_registers(motor_address, [0, 0])
            self._logger.info("Motor %s stopped", motor_address)
            return True
        except Exception:
            self._logger.exception("turn_off failed for motor %s", motor_address)
            return False

    def set_speed(self, motor_address: int, speed: int) -> bool:
        try:
            result = self._ramp(motor_address, speed, steps=1)
            if result:
                self._logger.debug("Motor %s speed → %s", motor_address, speed)
            return result
        except Exception:
            self._logger.exception("set_speed failed for motor %s", motor_address)
            return False

    def health_check(self, motor_address: int) -> MotorState:
        return self._health.check_motor(motor_address)

    def health_check_all(self, motor_addresses: List[int]) -> MotorsSnapshot:
        return self._health.check_all_motors(motor_addresses)

    def health_check_all_configured(self) -> MotorsSnapshot:
        return self._health.check_all_motors(self._config.motor_addresses)

    # ── Internal ──────────────────────────────────────────────────────

    def _ramp(self, motor_address: int, target: int, steps: int) -> bool:
        steps     = max(1, steps)
        increment = target // steps
        for i in range(steps):
            value     = increment * (i + 1)
            high, low = split_into_16bit(value)
            try:
                self._transport.write_registers(motor_address, [low, high])
            except Exception:
                self._logger.exception(
                    "Ramp step %d/%d failed for motor %s", i + 1, steps, motor_address
                )
                return False
            if self._config.ramp_step_delay_s > 0:
                time.sleep(self._config.ramp_step_delay_s)
        return True
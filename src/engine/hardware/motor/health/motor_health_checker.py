from __future__ import annotations
import logging
import time
from typing import Dict, List

from src.engine.hardware.motor.interfaces.i_motor_transport import IMotorTransport
from src.engine.hardware.motor.models.motor_config import MotorConfig
from src.engine.hardware.motor.models.motor_state import MotorState, MotorsSnapshot


class MotorHealthChecker:
    """
    Performs health-check cycles against a motor controller board.
    Depends only on IMotorTransport — knows nothing about Modbus or serial ports.
    """

    def __init__(self, transport: IMotorTransport, config: MotorConfig) -> None:
        self._transport = transport
        self._config    = config
        self._logger    = logging.getLogger(self.__class__.__name__)

    # ── Public ────────────────────────────────────────────────────────

    def check_motor(self, motor_address: int) -> MotorState:
        state = MotorState(motor_address=motor_address)
        try:
            self._trigger_health_check()
            error_count = self._read_error_count()
            if error_count == 0:
                state.is_healthy = True
                return state
            raw_errors = self._read_error_values(error_count)
            relevant   = self._filter_for_motor(raw_errors, motor_address)
            if relevant:
                state.error_codes = relevant
                state.is_healthy  = False
                self._log_errors(motor_address, relevant)
            else:
                state.is_healthy = True
        except Exception as exc:
            self._logger.exception("Health check failed for motor %s", motor_address)
            state.communication_errors.append(str(exc))
        return state

    def check_all_motors(self, motor_addresses: List[int]) -> MotorsSnapshot:
        snapshot = MotorsSnapshot(success=True)
        try:
            self._trigger_health_check()
            error_count = self._read_error_count()

            if error_count == 0:
                for addr in motor_addresses:
                    snapshot.add(MotorState(motor_address=addr, is_healthy=True))
                return snapshot

            raw_errors = self._read_error_values(error_count)
            for addr in motor_addresses:
                relevant = self._filter_for_motor(raw_errors, addr)
                state    = MotorState(motor_address=addr)
                if relevant:
                    state.error_codes = relevant
                    state.is_healthy  = False
                    self._log_errors(addr, relevant)
                else:
                    state.is_healthy = True
                snapshot.add(state)

        except Exception as exc:
            self._logger.exception("Bulk health check failed")
            snapshot.success = False
            for addr in motor_addresses:
                state = MotorState(motor_address=addr)
                state.communication_errors.append(str(exc))
                snapshot.add(state)
        return snapshot

    # ── Internal ──────────────────────────────────────────────────────

    def _trigger_health_check(self) -> None:
        self._transport.write_registers(
            self._config.health_check_trigger_register, [1]
        )
        time.sleep(self._config.health_check_delay_s)

    def _read_error_count(self) -> int:
        return self._transport.read_register(self._config.motor_error_count_register)

    def _read_error_values(self, count: int) -> List[int]:
        values = self._transport.read_registers(
            self._config.motor_error_registers_start, count
        )
        return [v for v in values if v != 0]

    def _filter_for_motor(self, raw_errors: List[int], motor_address: int) -> List[int]:
        prefix = self._config.address_to_error_prefix.get(motor_address)
        if prefix is None:
            return raw_errors
        return [e for e in raw_errors if e // 10 == prefix]

    def _log_errors(self, motor_address: int, error_codes: List[int]) -> None:
        from src.engine.hardware.motor.models.motor_error_codes import MotorErrorCode
        for code in error_codes:
            mc = MotorErrorCode.from_code(code)
            desc = mc.description() if mc else f"unknown({code})"
            self._logger.warning("Motor %s — %s", motor_address, desc)
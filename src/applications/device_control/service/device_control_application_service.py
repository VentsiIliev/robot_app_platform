from __future__ import annotations
import logging
from typing import Dict, List, Optional

from src.engine.hardware.generator.interfaces.i_generator_controller import IGeneratorController
from src.engine.hardware.laser.i_laser_control import ILaserControl
from src.engine.hardware.motor.interfaces.i_motor_service import IMotorService
from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.applications.device_control.service.i_device_control_service import (
    IDeviceControlService, MotorEntry,
)

_logger = logging.getLogger(__name__)

_MOTOR_SPEED               = 10000
_MOTOR_RAMP_STEPS          = 1
_MOTOR_INITIAL_RAMP_SPEED  = 5000
_MOTOR_INITIAL_RAMP_DUR    = 1.0
_MOTOR_REVERSE_SPEED       = 1000
_MOTOR_REVERSE_DUR         = 1.0
_MOTOR_REVERSE_RAMP_STEPS  = 1


class DeviceControlApplicationService(IDeviceControlService):

    def __init__(
        self,
        motors:         List[MotorEntry],
        motor_service:  Optional[IMotorService]         = None,
        generator:      Optional[IGeneratorController]  = None,
        laser:          Optional[ILaserControl]         = None,
        vacuum_pump:    Optional[IVacuumPumpController] = None,
    ) -> None:
        self._motors    = list(motors)
        self._motor     = motor_service
        self._generator = generator
        self._laser     = laser
        self._vacuum    = vacuum_pump

    # ── Queries ───────────────────────────────────────────────────────

    def get_motors(self) -> List[MotorEntry]:
        return list(self._motors)

    def get_motor_health_snapshot(self) -> Dict[int, bool]:
        if not self._motor or not self._motor.is_healthy():
            return {m.address: False for m in self._motors}
        try:
            snapshot = self._motor.health_check_all_configured()
            return {
                m.address: (
                    snapshot.get_motor(m.address).is_healthy
                    if snapshot.get_motor(m.address) is not None
                    else False
                )
                for m in self._motors
            }
        except Exception:
            _logger.exception("get_motor_health_snapshot failed")
            return {m.address: False for m in self._motors}

    # ── Laser ─────────────────────────────────────────────────────────

    def laser_on(self) -> None:
        if self._laser:
            self._laser.turn_on()

    def laser_off(self) -> None:
        if self._laser:
            self._laser.turn_off()

    # ── Vacuum pump ───────────────────────────────────────────────────

    def vacuum_pump_on(self) -> bool:
        return self._vacuum.turn_on() if self._vacuum else False

    def vacuum_pump_off(self) -> bool:
        return self._vacuum.turn_off() if self._vacuum else False

    # ── Motor ─────────────────────────────────────────────────────────

    def motor_on(self, address: int) -> bool:
        if not self._motor:
            return False
        if not any(m.address == address for m in self._motors):
            _logger.warning("motor_on: address %s not in configured motors", address)
            return False
        try:
            return self._motor.turn_on(
                motor_address               = address,
                speed                       = _MOTOR_SPEED,
                ramp_steps                  = _MOTOR_RAMP_STEPS,
                initial_ramp_speed          = _MOTOR_INITIAL_RAMP_SPEED,
                initial_ramp_speed_duration = _MOTOR_INITIAL_RAMP_DUR,
            )
        except Exception:
            _logger.exception("motor_on failed (address=%s)", address)
            return False

    def motor_off(self, address: int) -> bool:
        if not self._motor:
            return False
        if not any(m.address == address for m in self._motors):
            _logger.warning("motor_off: address %s not in configured motors", address)
            return False
        try:
            return self._motor.turn_off(
                motor_address    = address,
                speed_reverse    = _MOTOR_REVERSE_SPEED,
                reverse_duration = _MOTOR_REVERSE_DUR,
                ramp_steps       = _MOTOR_REVERSE_RAMP_STEPS,
            )
        except Exception:
            _logger.exception("motor_off failed (address=%s)", address)
            return False

    # ── Generator ─────────────────────────────────────────────────────

    def generator_on(self) -> bool:
        if not self._generator:
            return False
        try:
            return self._generator.turn_on()
        except Exception:
            _logger.exception("generator_on failed")
            return False

    def generator_off(self) -> bool:
        if not self._generator:
            return False
        try:
            return self._generator.turn_off()
        except Exception:
            _logger.exception("generator_off failed")
            return False

    # ── Availability ──────────────────────────────────────────────────

    def is_laser_available(self) -> bool:
        return self._laser is not None

    def is_vacuum_pump_available(self) -> bool:
        return self._vacuum is not None

    def is_motor_available(self) -> bool:
        return self._motor is not None and self._motor.is_healthy()

    def is_generator_available(self) -> bool:
        return self._generator is not None


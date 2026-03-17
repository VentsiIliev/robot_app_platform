from __future__ import annotations
import logging
from typing import Optional

from src.engine.hardware.motor.interfaces.i_motor_service import IMotorService
from src.robot_systems.glue.processes.glue_dispensing.dispensing_settings import (
    DispensingSegmentSettings,
)

_logger = logging.getLogger(__name__)


class GluePumpController:
    """
    Adapter between the dispensing process and IMotorService.
    Reads motor parameters from per-segment settings dict or falls back to
    a GlueSettings dataclass when use_segment_settings=False.
    """

    def __init__(
        self,
        motor_service:        IMotorService,
        use_segment_settings: bool = True,
        fallback_settings     = None,   # Optional[GlueSettings]
    ) -> None:
        self._motor       = motor_service
        self._use_segment = use_segment_settings
        self._fallback    = fallback_settings
        self._last_exception: Exception | None = None

    def get_last_exception(self) -> Exception | None:
        return self._last_exception

    def pump_on(self, motor_address: int, settings: Optional[DispensingSegmentSettings] = None) -> bool:
        effective = settings if (self._use_segment and settings) else None
        try:
            if effective:
                self._last_exception = None
                return self._motor.turn_on(
                    motor_address               = motor_address,
                    speed                       = effective.motor_speed,
                    ramp_steps                  = effective.forward_ramp_steps,
                    initial_ramp_speed          = effective.initial_ramp_speed,
                    initial_ramp_speed_duration = effective.initial_ramp_speed_duration,
                )
            fb = self._fallback
            self._last_exception = None
            return self._motor.turn_on(
                motor_address               = motor_address,
                speed                       = fb.motor_speed                 if fb else 10000,
                ramp_steps                  = fb.forward_ramp_steps          if fb else 1,
                initial_ramp_speed          = fb.initial_ramp_speed          if fb else 5000,
                initial_ramp_speed_duration = fb.initial_ramp_speed_duration if fb else 1.0,
            )
        except Exception as exc:
            self._last_exception = exc
            _logger.exception("pump_on failed (motor_address=%s)", motor_address)
            return False

    def pump_off(self, motor_address: int, settings: Optional[DispensingSegmentSettings] = None) -> bool:
        effective = settings if (self._use_segment and settings) else None
        try:
            if effective:
                self._last_exception = None
                return self._motor.turn_off(
                    motor_address    = motor_address,
                    speed_reverse    = effective.speed_reverse,
                    reverse_duration = effective.reverse_duration,
                    ramp_steps       = effective.reverse_ramp_steps,
                )
            fb = self._fallback
            self._last_exception = None
            return self._motor.turn_off(
                motor_address    = motor_address,
                speed_reverse    = fb.speed_reverse     if fb else 1000,
                reverse_duration = fb.reverse_duration  if fb else 1.0,
                ramp_steps       = fb.reverse_ramp_steps if fb else 1,
            )
        except Exception as exc:
            self._last_exception = exc
            _logger.exception("pump_off failed (motor_address=%s)", motor_address)
            return False

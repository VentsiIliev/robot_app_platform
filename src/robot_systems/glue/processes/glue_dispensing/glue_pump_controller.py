from __future__ import annotations
import logging
from typing import Optional

from src.engine.hardware.motor.interfaces.i_motor_service import IMotorService
from src.robot_systems.glue.settings.glue import GlueSettingKey

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

    def pump_on(self, motor_address: int, settings: Optional[dict] = None) -> bool:
        effective = settings if (self._use_segment and settings) else None
        try:
            if effective:
                return self._motor.turn_on(
                    motor_address               = motor_address,
                    speed                       = int(float(effective.get(GlueSettingKey.MOTOR_SPEED.value, 0))),
                    ramp_steps                  = int(float(effective.get(GlueSettingKey.FORWARD_RAMP_STEPS.value, 1))),
                    initial_ramp_speed          = int(float(effective.get(GlueSettingKey.INITIAL_RAMP_SPEED.value, 0))),
                    initial_ramp_speed_duration = float(effective.get(GlueSettingKey.INITIAL_RAMP_SPEED_DURATION.value, 1.0)),
                )
            fb = self._fallback
            return self._motor.turn_on(
                motor_address               = motor_address,
                speed                       = fb.motor_speed                 if fb else 10000,
                ramp_steps                  = fb.forward_ramp_steps          if fb else 1,
                initial_ramp_speed          = fb.initial_ramp_speed          if fb else 5000,
                initial_ramp_speed_duration = fb.initial_ramp_speed_duration if fb else 1.0,
            )
        except Exception:
            _logger.exception("pump_on failed (motor_address=%s)", motor_address)
            return False

    def pump_off(self, motor_address: int, settings: Optional[dict] = None) -> bool:
        effective = settings if (self._use_segment and settings) else None
        try:
            if effective:
                return self._motor.turn_off(
                    motor_address    = motor_address,
                    speed_reverse    = int(float(effective.get(GlueSettingKey.SPEED_REVERSE.value, 0))),
                    reverse_duration = float(effective.get(GlueSettingKey.REVERSE_DURATION.value, 0)),
                    ramp_steps       = int(float(effective.get(GlueSettingKey.REVERSE_RAMP_STEPS.value, 1))),
                )
            fb = self._fallback
            return self._motor.turn_off(
                motor_address    = motor_address,
                speed_reverse    = fb.speed_reverse     if fb else 1000,
                reverse_duration = fb.reverse_duration  if fb else 1.0,
                ramp_steps       = fb.reverse_ramp_steps if fb else 1,
            )
        except Exception:
            _logger.exception("pump_off failed (motor_address=%s)", motor_address)
            return False


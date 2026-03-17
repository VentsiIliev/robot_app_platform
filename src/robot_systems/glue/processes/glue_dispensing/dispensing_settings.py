from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.robot_systems.glue.settings.glue import GlueSettingKey


@dataclass(slots=True)
class DispensingSegmentSettings:
    glue_type: str | None = None
    velocity: float | None = None
    acceleration: float | None = None
    reach_start_threshold: float = 1.0
    reach_end_threshold: float = 1.0
    motor_speed: int = 0
    forward_ramp_steps: int = 1
    initial_ramp_speed: int = 0
    initial_ramp_speed_duration: float = 1.0
    speed_reverse: int = 0
    reverse_duration: float = 0.0
    reverse_ramp_steps: int = 1
    glue_speed_coefficient: float = 5.0
    glue_acceleration_coefficient: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw_settings: Any) -> "DispensingSegmentSettings":
        if isinstance(raw_settings, cls):
            return raw_settings

        data = dict(raw_settings or {})
        used_keys = {
            GlueSettingKey.GLUE_TYPE.value,
            "velocity",
            "acceleration",
            GlueSettingKey.REACH_START_THRESHOLD.value,
            GlueSettingKey.REACH_END_THRESHOLD.value,
            GlueSettingKey.MOTOR_SPEED.value,
            GlueSettingKey.FORWARD_RAMP_STEPS.value,
            GlueSettingKey.INITIAL_RAMP_SPEED.value,
            GlueSettingKey.INITIAL_RAMP_SPEED_DURATION.value,
            GlueSettingKey.SPEED_REVERSE.value,
            GlueSettingKey.REVERSE_DURATION.value,
            GlueSettingKey.REVERSE_RAMP_STEPS.value,
            "glue_speed_coefficient",
            "glue_acceleration_coefficient",
        }
        return cls(
            glue_type=data.get(GlueSettingKey.GLUE_TYPE.value),
            velocity=_optional_float(data.get("velocity")),
            acceleration=_optional_float(data.get("acceleration")),
            reach_start_threshold=float(data.get(GlueSettingKey.REACH_START_THRESHOLD.value, 1.0)),
            reach_end_threshold=float(data.get(GlueSettingKey.REACH_END_THRESHOLD.value, 1.0)),
            motor_speed=int(float(data.get(GlueSettingKey.MOTOR_SPEED.value, 0))),
            forward_ramp_steps=int(float(data.get(GlueSettingKey.FORWARD_RAMP_STEPS.value, 1))),
            initial_ramp_speed=int(float(data.get(GlueSettingKey.INITIAL_RAMP_SPEED.value, 0))),
            initial_ramp_speed_duration=float(data.get(GlueSettingKey.INITIAL_RAMP_SPEED_DURATION.value, 1.0)),
            speed_reverse=int(float(data.get(GlueSettingKey.SPEED_REVERSE.value, 0))),
            reverse_duration=float(data.get(GlueSettingKey.REVERSE_DURATION.value, 0.0)),
            reverse_ramp_steps=int(float(data.get(GlueSettingKey.REVERSE_RAMP_STEPS.value, 1))),
            glue_speed_coefficient=float(data.get("glue_speed_coefficient", 5)),
            glue_acceleration_coefficient=float(data.get("glue_acceleration_coefficient", 0)),
            extra={k: v for k, v in data.items() if k not in used_keys},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            GlueSettingKey.GLUE_TYPE.value: self.glue_type,
            "velocity": self.velocity,
            "acceleration": self.acceleration,
            GlueSettingKey.REACH_START_THRESHOLD.value: self.reach_start_threshold,
            GlueSettingKey.REACH_END_THRESHOLD.value: self.reach_end_threshold,
            GlueSettingKey.MOTOR_SPEED.value: self.motor_speed,
            GlueSettingKey.FORWARD_RAMP_STEPS.value: self.forward_ramp_steps,
            GlueSettingKey.INITIAL_RAMP_SPEED.value: self.initial_ramp_speed,
            GlueSettingKey.INITIAL_RAMP_SPEED_DURATION.value: self.initial_ramp_speed_duration,
            GlueSettingKey.SPEED_REVERSE.value: self.speed_reverse,
            GlueSettingKey.REVERSE_DURATION.value: self.reverse_duration,
            GlueSettingKey.REVERSE_RAMP_STEPS.value: self.reverse_ramp_steps,
            "glue_speed_coefficient": self.glue_speed_coefficient,
            "glue_acceleration_coefficient": self.glue_acceleration_coefficient,
            **self.extra,
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return self == DispensingSegmentSettings.from_raw(other)
        if isinstance(other, DispensingSegmentSettings):
            return self.to_dict() == other.to_dict()
        return NotImplemented


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

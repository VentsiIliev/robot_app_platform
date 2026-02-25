from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


class GlueSettingKey(Enum):
    SPRAY_WIDTH                          = "spray_width"
    SPRAYING_HEIGHT                      = "spraying_height"
    FAN_SPEED                            = "fan_speed"
    TIME_BETWEEN_GENERATOR_AND_GLUE      = "time_between_generator_and_glue"
    MOTOR_SPEED                          = "motor_speed"
    REVERSE_DURATION                     = "reverse_duration"
    SPEED_REVERSE                        = "speed_reverse"
    RZ_ANGLE                             = "rz_angle"
    GLUE_TYPE                            = "glue_type"
    GENERATOR_TIMEOUT                    = "generator_timeout"
    TIME_BEFORE_MOTION                   = "time_before_motion"
    TIME_BEFORE_STOP                     = "time_before_stop"
    REACH_START_THRESHOLD                = "reach_start_threshold"
    REACH_END_THRESHOLD                  = "reach_end_threshold"
    INITIAL_RAMP_SPEED                   = "initial_ramp_speed"
    FORWARD_RAMP_STEPS                   = "forward_ramp_steps"
    REVERSE_RAMP_STEPS                   = "reverse_ramp_steps"
    INITIAL_RAMP_SPEED_DURATION          = "initial_ramp_speed_duration"
    SPRAY_ON                             = "spray_on"


@dataclass
class GlueSettings:
    spray_width: int                         = 5
    spraying_height: int                     = 10
    fan_speed: int                           = 50
    time_between_generator_and_glue: float   = 1.0
    motor_speed: int                         = 10000
    reverse_duration: float                  = 1.0
    speed_reverse: int                       = 1000
    rz_angle: float                          = 0.0
    glue_type: str                           = "Type A"
    generator_timeout: float                 = 5.0
    time_before_motion: float                = 1.0
    time_before_stop: float                  = 1.0
    reach_start_threshold: float             = 1.0
    reach_end_threshold: float               = 1.0
    initial_ramp_speed: int                  = 5000
    forward_ramp_steps: int                  = 1
    reverse_ramp_steps: int                  = 1
    initial_ramp_speed_duration: float       = 1.0
    spray_on: bool                           = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GlueSettings':
        return cls(
            spray_width=data.get(GlueSettingKey.SPRAY_WIDTH.value, 5),
            spraying_height=data.get(GlueSettingKey.SPRAYING_HEIGHT.value, 10),
            fan_speed=data.get(GlueSettingKey.FAN_SPEED.value, 50),
            time_between_generator_and_glue=data.get(GlueSettingKey.TIME_BETWEEN_GENERATOR_AND_GLUE.value, 1.0),
            motor_speed=data.get(GlueSettingKey.MOTOR_SPEED.value, 10000),
            reverse_duration=data.get(GlueSettingKey.REVERSE_DURATION.value, 1.0),
            speed_reverse=data.get(GlueSettingKey.SPEED_REVERSE.value, 1000),
            rz_angle=data.get(GlueSettingKey.RZ_ANGLE.value, 0.0),
            glue_type=data.get(GlueSettingKey.GLUE_TYPE.value, "Type A"),
            generator_timeout=data.get(GlueSettingKey.GENERATOR_TIMEOUT.value, 5.0),
            time_before_motion=data.get(GlueSettingKey.TIME_BEFORE_MOTION.value, 1.0),
            time_before_stop=data.get(GlueSettingKey.TIME_BEFORE_STOP.value, 1.0),
            reach_start_threshold=data.get(GlueSettingKey.REACH_START_THRESHOLD.value, 1.0),
            reach_end_threshold=data.get(GlueSettingKey.REACH_END_THRESHOLD.value, 1.0),
            initial_ramp_speed=data.get(GlueSettingKey.INITIAL_RAMP_SPEED.value, 5000),
            forward_ramp_steps=data.get(GlueSettingKey.FORWARD_RAMP_STEPS.value, 1),
            reverse_ramp_steps=data.get(GlueSettingKey.REVERSE_RAMP_STEPS.value, 1),
            initial_ramp_speed_duration=data.get(GlueSettingKey.INITIAL_RAMP_SPEED_DURATION.value, 1.0),
            spray_on=data.get(GlueSettingKey.SPRAY_ON.value, True),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            GlueSettingKey.SPRAY_WIDTH.value:                     self.spray_width,
            GlueSettingKey.SPRAYING_HEIGHT.value:                 self.spraying_height,
            GlueSettingKey.FAN_SPEED.value:                       self.fan_speed,
            GlueSettingKey.TIME_BETWEEN_GENERATOR_AND_GLUE.value: self.time_between_generator_and_glue,
            GlueSettingKey.MOTOR_SPEED.value:                     self.motor_speed,
            GlueSettingKey.REVERSE_DURATION.value:                self.reverse_duration,
            GlueSettingKey.SPEED_REVERSE.value:                   self.speed_reverse,
            GlueSettingKey.RZ_ANGLE.value:                        self.rz_angle,
            GlueSettingKey.GLUE_TYPE.value:                       self.glue_type,
            GlueSettingKey.GENERATOR_TIMEOUT.value:               self.generator_timeout,
            GlueSettingKey.TIME_BEFORE_MOTION.value:              self.time_before_motion,
            GlueSettingKey.TIME_BEFORE_STOP.value:                self.time_before_stop,
            GlueSettingKey.REACH_START_THRESHOLD.value:           self.reach_start_threshold,
            GlueSettingKey.REACH_END_THRESHOLD.value:             self.reach_end_threshold,
            GlueSettingKey.INITIAL_RAMP_SPEED.value:              self.initial_ramp_speed,
            GlueSettingKey.FORWARD_RAMP_STEPS.value:              self.forward_ramp_steps,
            GlueSettingKey.REVERSE_RAMP_STEPS.value:              self.reverse_ramp_steps,
            GlueSettingKey.INITIAL_RAMP_SPEED_DURATION.value:     self.initial_ramp_speed_duration,
            GlueSettingKey.SPRAY_ON.value:                        self.spray_on,
        }

    def __str__(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=4)


class GlueSettingsSerializer(ISettingsSerializer[GlueSettings]):

    @property
    def settings_type(self) -> str:
        return "glue_settings"

    def get_default(self) -> GlueSettings:
        return GlueSettings()

    def to_dict(self, settings: GlueSettings) -> Dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: Dict[str, Any]) -> GlueSettings:
        return GlueSettings.from_dict(data)

from copy import deepcopy

from src.robot_apps.glue.settings.glue import GlueSettings


class GlueSettingsMapper:

    @staticmethod
    def to_flat_dict(settings: GlueSettings) -> dict:
        return {
            "spray_width":                     settings.spray_width,
            "spraying_height":                 settings.spraying_height,
            "fan_speed":                       settings.fan_speed,
            "time_between_generator_and_glue": settings.time_between_generator_and_glue,
            "motor_speed":                     settings.motor_speed,
            "reverse_duration":                settings.reverse_duration,
            "speed_reverse":                   settings.speed_reverse,
            "rz_angle":                        settings.rz_angle,
            "glue_type":                       settings.glue_type,
            "generator_timeout":               settings.generator_timeout,
            "time_before_motion":              settings.time_before_motion,
            "time_before_stop":                settings.time_before_stop,
            "reach_start_threshold":           settings.reach_start_threshold,
            "reach_end_threshold":             settings.reach_end_threshold,
            "initial_ramp_speed":              settings.initial_ramp_speed,
            "forward_ramp_steps":              settings.forward_ramp_steps,
            "reverse_ramp_steps":              settings.reverse_ramp_steps,
            "initial_ramp_speed_duration":     settings.initial_ramp_speed_duration,
            "spray_on":                        settings.spray_on,
        }

    @staticmethod
    def from_flat_dict(flat: dict, base: GlueSettings) -> GlueSettings:
        s = deepcopy(base)
        s.spray_width                     = float(flat.get("spray_width",                     s.spray_width))
        s.spraying_height                 = float(flat.get("spraying_height",                 s.spraying_height))
        s.fan_speed                       = float(flat.get("fan_speed",                       s.fan_speed))
        s.time_between_generator_and_glue = float(flat.get("time_between_generator_and_glue", s.time_between_generator_and_glue))
        s.motor_speed                     = float(flat.get("motor_speed",                     s.motor_speed))
        s.reverse_duration                = float(flat.get("reverse_duration",                s.reverse_duration))
        s.speed_reverse                   = float(flat.get("speed_reverse",                   s.speed_reverse))
        s.rz_angle                        = float(flat.get("rz_angle",                        s.rz_angle))
        s.glue_type                       = flat.get("glue_type",                             s.glue_type)
        s.generator_timeout               = float(flat.get("generator_timeout",               s.generator_timeout))
        s.time_before_motion              = float(flat.get("time_before_motion",              s.time_before_motion))
        s.time_before_stop                = float(flat.get("time_before_stop",                s.time_before_stop))
        s.reach_start_threshold           = float(flat.get("reach_start_threshold",           s.reach_start_threshold))
        s.reach_end_threshold             = float(flat.get("reach_end_threshold",             s.reach_end_threshold))
        s.initial_ramp_speed              = float(flat.get("initial_ramp_speed",              s.initial_ramp_speed))
        s.forward_ramp_steps              = int(flat.get("forward_ramp_steps",                s.forward_ramp_steps))
        s.reverse_ramp_steps              = int(flat.get("reverse_ramp_steps",                s.reverse_ramp_steps))
        s.initial_ramp_speed_duration     = float(flat.get("initial_ramp_speed_duration",     s.initial_ramp_speed_duration))
        s.spray_on                        = bool(flat.get("spray_on",                         s.spray_on))
        return s
from contour_editor import ISettingsProvider

from src.robot_systems.glue.settings.glue import GlueSettingKey

# RobotSettingKey does not exist in this codebase — plain strings
_VELOCITY_KEY     = "velocity"
_ACCELERATION_KEY = "acceleration"

# Keys not yet in GlueSettingKey enum — plain strings
_GLUE_SPEED_COEFF     = "glue_speed_coefficient"
_GLUE_ACC_COEFF       = "glue_acceleration_coefficient"
_ADAPTIVE_SPACING     = "adaptive_spacing_mm"
_SPLINE_DENSITY       = "spline_density_multiplier"
_SMOOTHING_LAMBDA     = "smoothing_lambda"


class SegmentSettingsProvider(ISettingsProvider):

    def __init__(self, material_types=None):
        self._default_settings = {
            GlueSettingKey.SPRAY_WIDTH.value:                     "10",
            GlueSettingKey.SPRAYING_HEIGHT.value:                 "0",
            GlueSettingKey.FAN_SPEED.value:                       "100",
            GlueSettingKey.TIME_BETWEEN_GENERATOR_AND_GLUE.value: "1",
            GlueSettingKey.MOTOR_SPEED.value:                     "500",
            GlueSettingKey.REVERSE_DURATION.value:                "0.5",
            GlueSettingKey.SPEED_REVERSE.value:                   "3000",
            GlueSettingKey.RZ_ANGLE.value:                        "0",
            GlueSettingKey.GLUE_TYPE.value:                       "",
            GlueSettingKey.GENERATOR_TIMEOUT.value:               "5",
            GlueSettingKey.TIME_BEFORE_MOTION.value:              "0.1",
            GlueSettingKey.TIME_BEFORE_STOP.value:                "1.0",
            GlueSettingKey.REACH_START_THRESHOLD.value:           "1.0",
            GlueSettingKey.REACH_END_THRESHOLD.value:             "30.0",
            GlueSettingKey.INITIAL_RAMP_SPEED_DURATION.value:     "1.0",
            GlueSettingKey.INITIAL_RAMP_SPEED.value:              "5000",
            GlueSettingKey.REVERSE_RAMP_STEPS.value:              "1",
            GlueSettingKey.FORWARD_RAMP_STEPS.value:              "3",
            _GLUE_SPEED_COEFF:                                    "5",
            _GLUE_ACC_COEFF:                                      "0",
            _ADAPTIVE_SPACING:                                    "10",
            _SPLINE_DENSITY:                                      "2.0",
            _SMOOTHING_LAMBDA:                                    "0.0",
            _VELOCITY_KEY:                                        "60",
            _ACCELERATION_KEY:                                    "30",
        }
        self._material_types = material_types or ["Type A"]

    def get_all_setting_keys(self):   return list(self._default_settings.keys())
    def get_default_values(self):     return self._default_settings.copy()
    def get_material_type_key(self):  return GlueSettingKey.GLUE_TYPE.value
    def get_available_material_types(self): return self._material_types
    def get_default_material_type(self):    return self._material_types[0] if self._material_types else ""
    def get_setting_label(self, key: str):  return key.replace("_", " ").title()
    def get_setting_value(self, key: str):  return self._default_settings.get(key)
    def validate_setting(self, key: str, value: str) -> bool:
        if key == GlueSettingKey.GLUE_TYPE.value: return bool(value)
        try: float(value); return True
        except (ValueError, TypeError): return False
    def validate_setting_value(self, key: str, value: str) -> bool:
        return self.validate_setting(key, value)
    def get_settings_tabs_config(self):
        return [("Settings", list(self._default_settings.keys()))]

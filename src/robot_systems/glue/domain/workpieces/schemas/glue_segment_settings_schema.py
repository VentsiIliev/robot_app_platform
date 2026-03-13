from src.applications.workpiece_editor.editor_core.config.segment_settings_schema import (
    SegmentSettingsSchema, SegmentSettingSpec,
)
from src.robot_systems.glue.settings.glue import GlueSettingKey


def build_glue_segment_settings_schema(glue_types: list) -> SegmentSettingsSchema:
    return SegmentSettingsSchema(
        combo_key = GlueSettingKey.GLUE_TYPE.value,
        combo_options    = glue_types or ["Type A"],
        fields=[
            # General
            SegmentSettingSpec(GlueSettingKey.SPRAY_WIDTH.value,                     "Spray Width",              "10",    "General"),
            SegmentSettingSpec(GlueSettingKey.SPRAYING_HEIGHT.value,                 "Spraying Height",          "20",     "General"),
            SegmentSettingSpec(GlueSettingKey.GLUE_TYPE.value,                       "Glue Type",                "",      "General",   validator="material_type"),
            # Forward Motion
            SegmentSettingSpec(GlueSettingKey.FORWARD_RAMP_STEPS.value,             "Forward Ramp Steps",       "3",     "Forward Motion"),
            SegmentSettingSpec(GlueSettingKey.INITIAL_RAMP_SPEED.value,             "Initial Ramp Speed",       "5000",  "Forward Motion"),
            SegmentSettingSpec(GlueSettingKey.INITIAL_RAMP_SPEED_DURATION.value,    "Initial Ramp Duration",    "1.0",   "Forward Motion"),
            SegmentSettingSpec(GlueSettingKey.MOTOR_SPEED.value,                    "Motor Speed",              "500",   "Forward Motion"),
            # Reverse Motion
            SegmentSettingSpec(GlueSettingKey.REVERSE_DURATION.value,               "Reverse Duration",         "0.5",   "Reverse Motion"),
            SegmentSettingSpec(GlueSettingKey.SPEED_REVERSE.value,                  "Reverse Speed",            "3000",  "Reverse Motion"),
            SegmentSettingSpec(GlueSettingKey.REVERSE_RAMP_STEPS.value,             "Reverse Ramp Steps",       "1",     "Reverse Motion"),
            # Robot
            SegmentSettingSpec("velocity",                                           "Velocity",                 "60",    "Robot"),
            SegmentSettingSpec("acceleration",                                       "Acceleration",             "30",    "Robot"),
            SegmentSettingSpec(GlueSettingKey.RZ_ANGLE.value,                       "Rz Angle",                 "0",     "Robot"),
            SegmentSettingSpec("adaptive_spacing_mm",                                "Adaptive Spacing (mm)",    "10",    "Robot"),
            SegmentSettingSpec("spline_density_multiplier",                          "Spline Density",           "2.0",   "Robot"),
            SegmentSettingSpec("smoothing_lambda",                                   "Smoothing Lambda",         "0.0",   "Robot"),
            # Generator
            SegmentSettingSpec(GlueSettingKey.TIME_BETWEEN_GENERATOR_AND_GLUE.value,"Time Gen → Glue",          "1",     "Generator"),
            SegmentSettingSpec(GlueSettingKey.GENERATOR_TIMEOUT.value,              "Generator Timeout",        "5",     "Generator"),
            SegmentSettingSpec(GlueSettingKey.FAN_SPEED.value,                      "Fan Speed",                "100",   "Generator"),
            SegmentSettingSpec(GlueSettingKey.TIME_BEFORE_MOTION.value,             "Time Before Motion",       "0.1",   "Generator"),
            SegmentSettingSpec(GlueSettingKey.TIME_BEFORE_STOP.value,               "Time Before Stop",         "1.0",   "Generator"),
            # Thresholds
            SegmentSettingSpec(GlueSettingKey.REACH_START_THRESHOLD.value,          "Reach Start (mm)",         "1.0",   "Thresholds (mm)"),
            SegmentSettingSpec(GlueSettingKey.REACH_END_THRESHOLD.value,            "Reach End (mm)",           "30.0",  "Thresholds (mm)"),
            # Pump Speed
            SegmentSettingSpec("glue_speed_coefficient",                             "Speed Coefficient",        "5",     "Pump Speed"),
            SegmentSettingSpec("glue_acceleration_coefficient",                      "Acceleration Coefficient", "0",     "Pump Speed"),
        ],
    )
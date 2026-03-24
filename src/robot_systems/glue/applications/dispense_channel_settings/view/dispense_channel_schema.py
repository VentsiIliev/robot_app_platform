from __future__ import annotations

from pl_gui.settings.settings_view.schema import SettingField, SettingGroup


def build_glue_group(glue_types: list[str]) -> SettingGroup:
    choices = list(glue_types) if glue_types else [""]
    default = choices[0] if choices else ""
    return SettingGroup("Glue", [
        SettingField("glue_type", "Glue Type", "combo", default=default, choices=choices),
    ])


SCALE_GROUP = SettingGroup("Scale", [
    SettingField("url", "URL", "line_edit", default="http://192.168.1.100"),
    SettingField("capacity", "Capacity", "double_spinbox", default=1000.0, min_val=0.0, max_val=100000.0, decimals=1, suffix=" g", step=100.0),
    SettingField("fetch_timeout_seconds", "Fetch Timeout", "double_spinbox", default=5.0, min_val=0.1, max_val=60.0, decimals=1, suffix=" s", step=0.5),
    SettingField("data_fetch_interval_ms", "Fetch Interval", "spinbox", default=500, min_val=50, max_val=10000, suffix=" ms", step=50),
])

CALIBRATION_GROUP = SettingGroup("Calibration", [
    SettingField("zero_offset", "Zero Offset", "double_spinbox", default=0.0, min_val=-10000.0, max_val=10000.0, decimals=4, step=0.0001),
    SettingField("scale_factor", "Scale Factor", "double_spinbox", default=1.0, min_val=-1000.0, max_val=1000.0, decimals=6, step=0.000001),
])

MEASUREMENT_GROUP = SettingGroup("Measurement", [
    SettingField("sampling_rate", "Sampling Rate", "spinbox", default=10, min_val=1, max_val=1000, suffix=" Hz", step=1),
    SettingField("filter_cutoff", "Filter Cutoff", "double_spinbox", default=1.0, min_val=0.01, max_val=100.0, decimals=2, suffix=" Hz", step=0.1),
    SettingField("averaging_samples", "Averaging Samples", "spinbox", default=5, min_val=1, max_val=100, step=1),
    SettingField("min_weight_threshold", "Min Weight Threshold", "double_spinbox", default=0.0, min_val=0.0, max_val=100.0, decimals=2, suffix=" g", step=0.01),
    SettingField("max_weight_threshold", "Max Weight Threshold", "double_spinbox", default=1000.0, min_val=0.0, max_val=100000.0, decimals=1, suffix=" g", step=100.0),
])

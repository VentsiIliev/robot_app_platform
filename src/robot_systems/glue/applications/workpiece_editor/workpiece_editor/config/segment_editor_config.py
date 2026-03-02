from dataclasses import dataclass
from contour_editor import SettingsConfig, ISettingsProvider


@dataclass
class SegmentEditorConfig:
    """
    Bundles the per-segment settings panel configuration.
    Built by the robot system (e.g. application_wiring.py) — the workpiece editor
    itself never imports GlueSettingKey or any system-specific enum.
    """
    settings_config:   SettingsConfig
    settings_provider: ISettingsProvider


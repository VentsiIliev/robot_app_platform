from dataclasses import asdict

from src.engine.repositories.interfaces import ISettingsSerializer
from .incremental_adjustment import AdjustmentStep, DEFAULT_ADJUSTMENT_STEP


class PaintAdjustmentSettingsSerializer(ISettingsSerializer[AdjustmentStep]):
    @property
    def settings_type(self) -> str:
        return "paint_adjustment_settings"

    def get_default(self) -> AdjustmentStep:
        return DEFAULT_ADJUSTMENT_STEP

    def to_dict(self, settings: AdjustmentStep) -> dict:
        return asdict(settings)

    def from_dict(self, data: dict) -> AdjustmentStep:
        if not isinstance(data, dict):
            raise ValueError("Paint adjustment settings must be an object")
        unknown = set(data) - {"length_mm", "paint_axis_offset_mm", "perpendicular_axis_offset_mm"}
        if unknown:
            raise ValueError(f"Unknown paint adjustment settings: {sorted(unknown)}")
        return AdjustmentStep(**{**asdict(DEFAULT_ADJUSTMENT_STEP), **data})

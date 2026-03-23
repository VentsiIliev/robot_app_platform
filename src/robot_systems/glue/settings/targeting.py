from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.engine.repositories.interfaces import ISettingsSerializer


@dataclass
class GlueTargetingSettings:
    camera_center_x: float = 0.0
    camera_center_y: float = 0.0
    tool_point_x: float = 0.0
    tool_point_y: float = 0.0
    gripper_point_x: float = 0.0
    gripper_point_y: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlueTargetingSettings":
        return cls(
            camera_center_x=float(data.get("CAMERA_CENTER_X", 0.0)),
            camera_center_y=float(data.get("CAMERA_CENTER_Y", 0.0)),
            tool_point_x=float(data.get("TOOL_POINT_X", 0.0)),
            tool_point_y=float(data.get("TOOL_POINT_Y", 0.0)),
            gripper_point_x=float(data.get("GRIPPER_POINT_X", 0.0)),
            gripper_point_y=float(data.get("GRIPPER_POINT_Y", 0.0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "CAMERA_CENTER_X": self.camera_center_x,
            "CAMERA_CENTER_Y": self.camera_center_y,
            "TOOL_POINT_X": self.tool_point_x,
            "TOOL_POINT_Y": self.tool_point_y,
            "GRIPPER_POINT_X": self.gripper_point_x,
            "GRIPPER_POINT_Y": self.gripper_point_y,
        }


class GlueTargetingSettingsSerializer(ISettingsSerializer[GlueTargetingSettings]):
    @property
    def settings_type(self) -> str:
        return "glue_targeting"

    def get_default(self) -> GlueTargetingSettings:
        return GlueTargetingSettings()

    def to_dict(self, settings: GlueTargetingSettings) -> Dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: Dict[str, Any]) -> GlueTargetingSettings:
        return GlueTargetingSettings.from_dict(data)

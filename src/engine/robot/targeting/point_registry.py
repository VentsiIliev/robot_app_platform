from __future__ import annotations

from typing import Dict, List

from src.engine.robot.targeting.end_effector_point import EndEffectorPoint

CAMERA = "camera"
TOOL = "tool"
GRIPPER = "gripper"

_ALIASES: Dict[str, str] = {"camera_center": CAMERA}


class PointRegistry:
    """Build and store canonical end-effector points from measured point settings."""

    def __init__(self, point_settings=None) -> None:
        cam_x = float(getattr(point_settings, "camera_center_x", 0.0)) if point_settings else 0.0
        cam_y = float(getattr(point_settings, "camera_center_y", 0.0)) if point_settings else 0.0
        tool_x = float(getattr(point_settings, "tool_point_x", 0.0)) if point_settings else 0.0
        tool_y = float(getattr(point_settings, "tool_point_y", 0.0)) if point_settings else 0.0
        grip_x = float(getattr(point_settings, "gripper_point_x", 0.0)) if point_settings else 0.0
        grip_y = float(getattr(point_settings, "gripper_point_y", 0.0)) if point_settings else 0.0

        self._points: Dict[str, EndEffectorPoint] = {
            CAMERA: EndEffectorPoint(CAMERA, 0.0, 0.0),
            TOOL: EndEffectorPoint(TOOL, tool_x - cam_x, tool_y - cam_y),
            GRIPPER: EndEffectorPoint(GRIPPER, grip_x - cam_x, grip_y - cam_y),
        }

    def camera(self) -> EndEffectorPoint:
        return self._points[CAMERA]

    def tool(self) -> EndEffectorPoint:
        return self._points[TOOL]

    def gripper(self) -> EndEffectorPoint:
        return self._points[GRIPPER]

    def by_name(self, name: str) -> EndEffectorPoint:
        """Return the point for ``name``, resolving legacy aliases."""
        normalized = _ALIASES.get(str(name).strip().lower(), str(name).strip().lower())
        point = self._points.get(normalized)
        if point is None:
            raise ValueError(f"Unknown end-effector point '{name}'. Valid names: {list(self._points.keys())}")
        return point

    def names(self) -> List[str]:
        return list(self._points.keys())

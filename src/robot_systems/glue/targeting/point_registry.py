from __future__ import annotations

from typing import Dict, List, Optional

from src.robot_systems.glue.targeting.end_effector_point import EndEffectorPoint

# Canonical point names
CAMERA  = "camera"
TOOL    = "tool"
GRIPPER = "gripper"

# Accept legacy "camera_center" name from older config / UI code
_ALIASES: Dict[str, str] = {"camera_center": CAMERA}


class PointRegistry:
    """Builds and stores named end-effector points for the glue robot.

    Points are constructed from any object that carries the standard
    ``camera_center_x/y``, ``tool_point_x/y``, ``gripper_point_x/y``
    attributes (e.g. ``RobotSettings``, ``PickAndPlaceConfig``).

    Offsets stored on each ``EndEffectorPoint`` are the **local wrist-frame
    delta** from camera center to that point:

        offset = measured_point − camera_center

    The camera center always has ``(0.0, 0.0)`` offsets by definition.
    """

    def __init__(self, robot_config=None) -> None:
        cam_x = float(getattr(robot_config, "camera_center_x",  0.0)) if robot_config else 0.0
        cam_y = float(getattr(robot_config, "camera_center_y",  0.0)) if robot_config else 0.0
        tool_x = float(getattr(robot_config, "tool_point_x",    0.0)) if robot_config else 0.0
        tool_y = float(getattr(robot_config, "tool_point_y",    0.0)) if robot_config else 0.0
        grip_x = float(getattr(robot_config, "gripper_point_x", 0.0)) if robot_config else 0.0
        grip_y = float(getattr(robot_config, "gripper_point_y", 0.0)) if robot_config else 0.0

        self._points: Dict[str, EndEffectorPoint] = {
            CAMERA:  EndEffectorPoint(CAMERA,  0.0,             0.0),
            TOOL:    EndEffectorPoint(TOOL,    tool_x - cam_x,  tool_y - cam_y),
            GRIPPER: EndEffectorPoint(GRIPPER, grip_x - cam_x,  grip_y - cam_y),
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
            raise ValueError(
                f"Unknown end-effector point '{name}'. "
                f"Valid names: {list(self._points.keys())}"
            )
        return point

    def names(self) -> List[str]:
        return list(self._points.keys())

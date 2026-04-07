from __future__ import annotations

from src.engine.robot.targeting import EndEffectorPoint, PointRegistry
from typing import Iterable

def build_welding_point_registry(
    point_definitions: Iterable[dict],
) -> PointRegistry:
    points = list(point_definitions or [])
    point_map = {
        str(point.get("name", "")).strip().lower(): point
        for point in points
        if str(point.get("name", "")).strip()
    }
    camera_point = point_map.get("camera")
    cam_x = float(camera_point.get("x_mm", 0.0)) if camera_point is not None else 0.0
    cam_y = float(camera_point.get("y_mm", 0.0)) if camera_point is not None else 0.0

    return PointRegistry(
        points=[
            EndEffectorPoint(
                str(point["name"]),
                float(point.get("x_mm", 0.0)) - cam_x,
                float(point.get("y_mm", 0.0)) - cam_y,
            )
            for point in points
        ],
    )

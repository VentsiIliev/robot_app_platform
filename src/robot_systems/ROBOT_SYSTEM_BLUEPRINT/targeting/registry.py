from __future__ import annotations

from typing import Iterable

from src.engine.robot.targeting import EndEffectorPoint, PointRegistry


def build_my_point_registry(point_definitions: Iterable[dict]) -> PointRegistry:
    """TODO: Convert persisted target-point settings into a PointRegistry."""
    points_in = list(point_definitions or [])
    points = [
        EndEffectorPoint(
            name=str(point["name"]),
            offset_x=float(point.get("x_mm", 0.0)),
            offset_y=float(point.get("y_mm", 0.0)),
        )
        for point in points_in
    ]
    return PointRegistry(points=points)

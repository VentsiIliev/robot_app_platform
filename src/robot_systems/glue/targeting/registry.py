from __future__ import annotations

from src.engine.robot.targeting import EndEffectorPoint, PointRegistry
from src.robot_systems.glue.settings.targeting import GlueTargetingSettings
from src.robot_systems.glue.targeting.point_names import CAMERA_POINT


def build_glue_point_registry(targeting_settings: GlueTargetingSettings | None) -> PointRegistry:
    if targeting_settings is None:
        targeting_settings = GlueTargetingSettings.defaults()
    else:
        targeting_settings.ensure_defaults()

    point_map = {point.name: point for point in targeting_settings.points}
    camera_point = point_map.get(CAMERA_POINT)
    cam_x = float(camera_point.x_mm) if camera_point is not None else 0.0
    cam_y = float(camera_point.y_mm) if camera_point is not None else 0.0

    return PointRegistry(
        points=[
            EndEffectorPoint(
                point.name,
                float(point.x_mm) - cam_x,
                float(point.y_mm) - cam_y,
            )
            for point in targeting_settings.points
        ],
        aliases=targeting_settings.aliases,
    )

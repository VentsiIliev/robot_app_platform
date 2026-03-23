from __future__ import annotations

from src.engine.robot.targeting import EndEffectorPoint, PointRegistry


def build_my_point_registry(settings) -> PointRegistry:
    """TODO: Convert persisted target-point settings into a PointRegistry."""

    if settings is None:
        raise RuntimeError(
            "MyRobotSystem targeting settings are not loaded. "
            "Declare SettingsID.MY_TARGETING in settings_specs and load it in on_start()."
        )

    settings.ensure_defaults()
    points = [
        EndEffectorPoint(
            name=point.name,
            offset_x=point.x_mm,
            offset_y=point.y_mm,
        )
        for point in settings.points
    ]
    return PointRegistry(points=points, aliases=dict(settings.aliases))

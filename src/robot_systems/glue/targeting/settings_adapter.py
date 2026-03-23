from __future__ import annotations

from copy import deepcopy

from src.robot_systems.glue.settings.targeting import GlueTargetFrameDefinition, GlueTargetPoint, GlueTargetingSettings
from src.robot_systems.glue.targeting.targeting_constants import (
    CALIBRATION_FRAME,
    CAMERA_POINT,
    GRIPPER_POINT,
    PICKUP_FRAME,
    TOOL_POINT,
)


def to_editor_dict(settings: GlueTargetingSettings | None) -> dict:
    targeting = deepcopy(settings) if settings is not None else GlueTargetingSettings.defaults()
    targeting.ensure_defaults()
    return {
        "points": [
            {
                "name": point.name,
                "display_name": point.display_name or point.name,
                "x_mm": point.x_mm,
                "y_mm": point.y_mm,
                "aliases": sorted(alias for alias, target in targeting.aliases.items() if target == point.name),
            }
            for point in targeting.points
        ],
        "frames": [
            {
                "name": frame.name,
                "source_navigation_group": frame.source_navigation_group,
                "target_navigation_group": frame.target_navigation_group,
                "use_height_correction": frame.use_height_correction,
            }
            for frame in targeting.frames
        ],
        "protected_points": [CAMERA_POINT, TOOL_POINT, GRIPPER_POINT],
        "protected_frames": [CALIBRATION_FRAME, PICKUP_FRAME],
    }


def from_editor_dict(data: dict, base: GlueTargetingSettings | None) -> GlueTargetingSettings:
    points = [
        GlueTargetPoint(
            name=str(item.get("name", "")).strip().lower(),
            display_name=str(item.get("display_name", "")).strip(),
            x_mm=float(item.get("x_mm", 0.0)),
            y_mm=float(item.get("y_mm", 0.0)),
        )
        for item in data.get("points", [])
        if str(item.get("name", "")).strip()
    ]
    frames = [
        GlueTargetFrameDefinition(
            name=str(item.get("name", "")).strip().lower(),
            source_navigation_group=str(item.get("source_navigation_group", "")).strip(),
            target_navigation_group=str(item.get("target_navigation_group", "")).strip(),
            use_height_correction=bool(item.get("use_height_correction", False)),
        )
        for item in data.get("frames", [])
        if str(item.get("name", "")).strip()
    ]
    aliases = {}
    for item in data.get("points", []):
        name = str(item.get("name", "")).strip().lower()
        if not name:
            continue
        for alias in item.get("aliases", []):
            alias_name = str(alias).strip().lower()
            if alias_name:
                aliases[alias_name] = name
    settings = deepcopy(base) if base is not None else GlueTargetingSettings.defaults()
    settings.points = points
    settings.frames = frames
    settings.aliases = aliases
    settings.ensure_defaults()
    return settings

from __future__ import annotations

from copy import deepcopy

from src.engine.robot.targeting import (
    RemoteTcpDefinition,
    RemoteTcpSettings,
    TargetFrameDefinition,
    TargetFrameSettings,
    TargetingSettings,
)


def to_editor_dict(
    settings: TargetingSettings | None,
    point_definitions: list[RemoteTcpDefinition],
    frame_definitions: list[TargetFrameDefinition],
) -> dict:
    targeting = deepcopy(settings) if settings is not None else TargetingSettings.defaults()
    targeting.ensure_defaults()
    point_by_name = {str(point.name).strip().lower(): point for point in targeting.points}
    frame_by_name = {str(frame.name).strip().lower(): frame for frame in targeting.frames}
    return {
        "points": [
            {
                **definition.to_dict(),
                "display_name": (
                    str(getattr(point_by_name.get(str(definition.name).strip().lower()), "display_name", "")).strip()
                    or str(definition.display_name or definition.name)
                ),
                "x_mm": float(getattr(point_by_name.get(str(definition.name).strip().lower()), "x_mm", 0.0)),
                "y_mm": float(getattr(point_by_name.get(str(definition.name).strip().lower()), "y_mm", 0.0)),
            }
            for definition in point_definitions
        ],
        "frames": [
            {
                **definition.to_dict(),
                "source_navigation_group": (
                    str(getattr(frame_by_name.get(str(definition.name).strip().lower()), "source_navigation_group", "")).strip()
                    or str(definition.source_navigation_group).strip()
                ),
                "target_navigation_group": (
                    str(getattr(frame_by_name.get(str(definition.name).strip().lower()), "target_navigation_group", "")).strip()
                    or str(definition.target_navigation_group).strip()
                ),
                "use_height_correction": bool(
                    getattr(frame_by_name.get(str(definition.name).strip().lower()), "use_height_correction", definition.use_height_correction)
                ),
            }
            for definition in frame_definitions
        ],
        "protected_points": [definition.name for definition in point_definitions],
        "protected_frames": [definition.name for definition in frame_definitions],
    }


def from_editor_dict(
    data: dict,
    base: TargetingSettings | None,
    point_definitions: list[RemoteTcpDefinition],
    frame_definitions: list[TargetFrameDefinition],
) -> TargetingSettings:
    declared_point_names = {str(definition.name).strip().lower() for definition in point_definitions}
    declared_frame_names = {str(definition.name).strip().lower() for definition in frame_definitions}
    points = [
        RemoteTcpSettings(
            name=RemoteTcpDefinition.from_dict(item).name,
            display_name=RemoteTcpDefinition.from_dict(item).display_name,
            x_mm=float(item.get("x_mm", 0.0)),
            y_mm=float(item.get("y_mm", 0.0)),
        )
        for item in data.get("points", [])
        if str(item.get("name", "")).strip()
    ]
    frames = [
        TargetFrameSettings(
            name=TargetFrameDefinition.from_dict(item).name,
            source_navigation_group=TargetFrameDefinition.from_dict(item).source_navigation_group,
            target_navigation_group=TargetFrameDefinition.from_dict(item).target_navigation_group,
            use_height_correction=TargetFrameDefinition.from_dict(item).use_height_correction,
        )
        for item in data.get("frames", [])
        if str(item.get("name", "")).strip()
    ]
    settings = deepcopy(base) if base is not None else TargetingSettings.defaults()
    point_items_by_name = {
        str(item.get("name", "")).strip().lower(): item
        for item in data.get("points", [])
        if str(item.get("name", "")).strip()
    }
    frame_items_by_name = {
        str(item.get("name", "")).strip().lower(): item
        for item in data.get("frames", [])
        if str(item.get("name", "")).strip()
    }

    extra_points = [
        point for point in points if str(point.name).strip().lower() not in declared_point_names
    ]
    declared_points = []
    for definition in point_definitions:
        item = point_items_by_name.get(str(definition.name).strip().lower(), {})
        point_item = RemoteTcpDefinition.from_dict(item) if item else definition
        declared_points.append(
            RemoteTcpSettings(
                name=definition.name,
                display_name=point_item.display_name or str(definition.display_name or definition.name),
                x_mm=float(item.get("x_mm", 0.0)),
                y_mm=float(item.get("y_mm", 0.0)),
            )
        )

    extra_frames = [
        frame for frame in frames if str(frame.name).strip().lower() not in declared_frame_names
    ]
    declared_frames = []
    for definition in frame_definitions:
        item = frame_items_by_name.get(str(definition.name).strip().lower(), {})
        frame_item = TargetFrameDefinition.from_dict(item) if item else definition
        declared_frames.append(
            TargetFrameSettings(
                name=definition.name,
                source_navigation_group=frame_item.source_navigation_group or definition.source_navigation_group,
                target_navigation_group=frame_item.target_navigation_group or definition.target_navigation_group,
                use_height_correction=frame_item.use_height_correction if item else definition.use_height_correction,
                work_area_id=definition.work_area_id,
            )
        )

    settings.points = extra_points + declared_points
    settings.frames = extra_frames + declared_frames
    settings.ensure_defaults()
    return settings

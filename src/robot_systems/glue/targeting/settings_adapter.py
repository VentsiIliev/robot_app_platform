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
    point_by_name = {
        str(point.name).strip().lower(): point
        for point in targeting.points
    }
    frame_by_name = {
        str(frame.name).strip().lower(): frame
        for frame in targeting.frames
    }
    points = []
    for definition in point_definitions:
        persisted = point_by_name.get(str(definition.name).strip().lower())
        point_item = definition.to_dict()
        point_item["display_name"] = (
            str(getattr(persisted, "display_name", "")).strip()
            or str(definition.display_name or definition.name)
        )
        point_item["x_mm"] = float(getattr(persisted, "x_mm", 0.0))
        point_item["y_mm"] = float(getattr(persisted, "y_mm", 0.0))
        points.append(point_item)
    for point in targeting.points:
        if any(str(item["name"]).strip().lower() == str(point.name).strip().lower() for item in points):
            continue
        points.append(
            {
                "name": point.name,
                "display_name": point.display_name or point.name,
                "x_mm": point.x_mm,
                "y_mm": point.y_mm,
            }
        )

    frames = []
    for definition in frame_definitions:
        persisted = frame_by_name.get(str(definition.name).strip().lower())
        frame_item = definition.to_dict()
        frame_item["source_navigation_group"] = (
            str(getattr(persisted, "source_navigation_group", "")).strip()
            or str(definition.source_navigation_group).strip()
        )
        frame_item["target_navigation_group"] = (
            str(getattr(persisted, "target_navigation_group", "")).strip()
            or str(definition.target_navigation_group).strip()
        )
        frame_item["use_height_correction"] = bool(
            getattr(persisted, "use_height_correction", definition.use_height_correction)
        )
        frames.append(frame_item)
    for frame in targeting.frames:
        if any(str(item["name"]).strip().lower() == str(frame.name).strip().lower() for item in frames):
            continue
        frames.append(
            {
                "name": frame.name,
                "source_navigation_group": frame.source_navigation_group,
                "target_navigation_group": frame.target_navigation_group,
                "use_height_correction": frame.use_height_correction,
            }
        )

    return {
        "points": points,
        "frames": frames,
        "protected_points": [definition.name for definition in point_definitions],
        "protected_frames": [definition.name for definition in frame_definitions],
    }


def from_editor_dict(
        data: dict,
        base: TargetingSettings | None,
        point_definitions: list[RemoteTcpDefinition],
        frame_definitions: list[TargetFrameDefinition],
) -> TargetingSettings:
    declared_point_names = {
        str(definition.name).strip().lower()
        for definition in point_definitions
    }
    declared_frames_by_name = {
        str(definition.name).strip().lower(): definition
        for definition in frame_definitions
    }
    base_by_name = {
        str(frame.name).strip().lower(): frame
        for frame in ((base.frames if base is not None else None) or [])
    }
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
            work_area_id=getattr(
                base_by_name.get(str(item.get("name", "")).strip().lower()),
                "work_area_id",
                "",
            ),
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
        point
        for point in points
        if str(point.name).strip().lower() not in declared_point_names
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
        frame
        for frame in frames
        if str(frame.name).strip().lower() not in declared_frames_by_name
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

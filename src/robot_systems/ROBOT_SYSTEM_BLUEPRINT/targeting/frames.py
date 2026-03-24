from __future__ import annotations

from typing import Iterable

from src.engine.robot.targeting import TargetFrame, TargetFrameDefinition


def build_my_target_frames(
    frame_definitions: Iterable[TargetFrameDefinition] | None,
    navigation=None,
    height_correction=None,
) -> dict[str, TargetFrame]:
    """TODO: Convert persisted frame settings into runtime TargetFrame objects."""
    frames_in = list(frame_definitions or [])
    frames: dict[str, TargetFrame] = {}
    for frame in frames_in:
        mapper = None
        if navigation is not None and frame.source_navigation_group and frame.target_navigation_group:
            # TODO: Replace this with the real mapper builder your system uses.
            mapper = None
        frames[frame.name] = TargetFrame(
            name=frame.name,
            work_area_id=getattr(frame, "work_area_id", ""),
            mapper=mapper,
            height_correction=height_correction if frame.use_height_correction else None,
        )
    return frames

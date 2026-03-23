from __future__ import annotations

from src.engine.robot.targeting import TargetFrame


def build_my_target_frames(settings, navigation=None, height_correction=None) -> dict[str, TargetFrame]:
    """TODO: Convert persisted frame settings into runtime TargetFrame objects."""

    if settings is None:
        return {}

    settings.ensure_defaults()
    frames: dict[str, TargetFrame] = {}
    for frame in settings.frames:
        mapper = None
        if navigation is not None and frame.source_navigation_group and frame.target_navigation_group:
            # TODO: Replace this with the real mapper builder your system uses.
            mapper = None
        frames[frame.name] = TargetFrame(
            name=frame.name,
            mapper=mapper,
            height_correction=height_correction if frame.use_height_correction else None,
        )
    return frames

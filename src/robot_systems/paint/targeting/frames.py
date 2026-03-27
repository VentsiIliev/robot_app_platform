from __future__ import annotations

from typing import Dict, Iterable, Optional

from src.engine.robot.targeting import TargetFrame, TargetFrameDefinition
from src.engine.robot.plane_pose_mapper import PlanePoseMapper
from src.robot_systems.paint.navigation import PaintNavigationService


def build_paint_target_frames(
    frame_definitions: Iterable[TargetFrameDefinition] | None,
    navigation: Optional[PaintNavigationService],
    height_correction=None,
) -> Dict[str, TargetFrame]:
    definitions = list(frame_definitions or [])

    frames: Dict[str, TargetFrame] = {}
    for definition in definitions:
        mapper = _build_mapper(definition, navigation)
        frame_height_correction = (
            height_correction(definition.work_area_id)
            if definition.use_height_correction and callable(height_correction)
            else height_correction if definition.use_height_correction else None
        )
        frames[definition.name] = TargetFrame(
            definition.name,
            work_area_id=definition.work_area_id,
            mapper=mapper,
            height_correction=frame_height_correction,
        )

    return frames


def _build_mapper(
    definition: TargetFrameDefinition,
    navigation: Optional[PaintNavigationService],
) -> Optional[PlanePoseMapper]:
    if navigation is None:
        return None
    if not definition.source_navigation_group or not definition.target_navigation_group:
        return None
    try:
        source_position = navigation.get_group_position(definition.source_navigation_group)
        target_position = navigation.get_group_position(definition.target_navigation_group)
        if source_position is None or target_position is None:
            return None
        return PlanePoseMapper.from_positions(
            source_position=source_position,
            target_position=target_position,
        )
    except Exception:
        return None

from __future__ import annotations

from typing import Dict, Optional

from src.engine.robot.targeting import TargetFrame
from src.engine.robot.plane_pose_mapper import PlanePoseMapper
from src.robot_systems.glue.navigation import GlueNavigationService
from src.robot_systems.glue.settings.targeting import GlueTargetFrameDefinition, GlueTargetingSettings
from src.robot_systems.glue.targeting.targeting_constants import CALIBRATION_FRAME, PICKUP_FRAME


def build_glue_target_frames(
    targeting_settings: GlueTargetingSettings | None,
    navigation: Optional[GlueNavigationService],
    height_correction=None,
) -> Dict[str, TargetFrame]:
    if targeting_settings is None:
        targeting_settings = GlueTargetingSettings.defaults()
    else:
        targeting_settings.ensure_defaults()

    frames: Dict[str, TargetFrame] = {}
    for definition in targeting_settings.frames:
        mapper = _build_mapper(definition, navigation)
        frame_height_correction = height_correction if definition.use_height_correction else None
        frames[definition.name] = TargetFrame(
            definition.name,
            mapper=mapper,
            height_correction=frame_height_correction,
        )

    if CALIBRATION_FRAME not in frames:
        frames[CALIBRATION_FRAME] = TargetFrame(CALIBRATION_FRAME, height_correction=height_correction)
    if PICKUP_FRAME not in frames:
        pickup_def = GlueTargetFrameDefinition(
            name=PICKUP_FRAME,
            source_navigation_group="CALIBRATION",
            target_navigation_group="HOME",
            use_height_correction=False,
        )
        frames[PICKUP_FRAME] = TargetFrame(PICKUP_FRAME, mapper=_build_mapper(pickup_def, navigation))
    return frames


def _build_mapper(
    definition: GlueTargetFrameDefinition,
    navigation: Optional[GlueNavigationService],
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

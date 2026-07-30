from __future__ import annotations

import logging

from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.robot_systems.paint.applications.paint_motion_plane_setup.domain.plane_inference import Pose6D
from src.robot_systems.paint.applications.paint_motion_plane_setup.service.i_paint_motion_plane_setup_service import (
    IPaintMotionPlaneSetupService,
)

_logger = logging.getLogger(__name__)


class PaintMotionPlaneSetupService(IPaintMotionPlaneSetupService):
    def __init__(
        self,
        *,
        robot_service: IRobotService | None,
        navigation_service,
        paint_group_ids: list[str] | tuple[str, ...],
    ) -> None:
        self._robot = robot_service
        self._navigation = navigation_service
        self._paint_group_ids = [
            group_id
            for group_id in (str(value or "").strip() for value in paint_group_ids)
            if group_id
        ]

    def get_paint_group_ids(self) -> list[str]:
        return list(self._paint_group_ids)

    def get_current_pose(self) -> Pose6D:
        if self._robot is None:
            raise RuntimeError("Robot service is not available")
        return Pose6D.from_sequence(self._robot.get_current_position())

    def get_paint_pose(self, group_id: str | None = None) -> Pose6D | None:
        group = self._resolve_group_id(group_id)
        if self._navigation is None or not group:
            return None
        pose = self._navigation.get_group_position(group)
        if pose is None:
            return None
        return Pose6D.from_sequence(pose)

    def move_to_paint_pose(self, group_id: str | None = None) -> bool:
        group = self._resolve_group_id(group_id)
        if self._navigation is None:
            _logger.error("Paint motion plane setup cannot move: navigation service is not available")
            return False
        if not group:
            _logger.error("Paint motion plane setup cannot move: paint group id is empty")
            return False
        return bool(self._navigation.move_to_group(group))

    def _resolve_group_id(self, group_id: str | None) -> str:
        requested = str(group_id or "").strip()
        if requested:
            return requested
        return self._paint_group_ids[0] if self._paint_group_ids else ""

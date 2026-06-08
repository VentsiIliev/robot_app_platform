from __future__ import annotations

from abc import ABC, abstractmethod

from src.robot_systems.paint.applications.paint_motion_plane_setup.domain.plane_inference import Pose6D


class IPaintMotionPlaneSetupService(ABC):
    @abstractmethod
    def get_current_pose(self) -> Pose6D: ...

    @abstractmethod
    def get_paint_pose(self) -> Pose6D | None: ...

    @abstractmethod
    def move_to_paint_pose(self) -> bool: ...

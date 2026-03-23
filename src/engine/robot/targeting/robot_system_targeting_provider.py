from __future__ import annotations

from abc import ABC, abstractmethod
from src.engine.robot.targeting.point_registry import PointRegistry
from src.engine.robot.targeting.target_frame import TargetFrame


class RobotSystemTargetingProvider(ABC):
    """Robot-system adapter that supplies generic targeting runtime pieces."""

    @abstractmethod
    def build_point_registry(self) -> PointRegistry:
        ...

    @abstractmethod
    def build_frames(self) -> dict[str, TargetFrame]:
        ...

    @abstractmethod
    def get_target_options(self) -> list[tuple[str, str]]:
        ...

    @abstractmethod
    def get_default_target_name(self) -> str:
        ...

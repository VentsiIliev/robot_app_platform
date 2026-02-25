from abc import ABC, abstractmethod
from .i_motion_service import IMotionService
from .i_robot_lifecycle import IRobotLifecycle


class IRobotService(IMotionService, IRobotLifecycle, ABC):
    """Full robot service interface."""

    @abstractmethod
    def get_current_velocity(self) -> float:
        ...

    @abstractmethod
    def get_current_acceleration(self) -> float:
        ...

    @abstractmethod
    def get_state(self) -> str:
        ...

    @abstractmethod
    def get_state_topic(self) -> str:
        ...
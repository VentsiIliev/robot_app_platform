from abc import ABC, abstractmethod
from src.engine.core.i_health_checkable import IHealthCheckable
from .i_motion_service import IMotionService
from .i_robot_lifecycle import IRobotLifecycle


class IRobotService(IMotionService, IRobotLifecycle, IHealthCheckable, ABC):
    """Full robot service interface."""

    @abstractmethod
    def get_current_velocity(self) -> float: ...

    @abstractmethod
    def get_current_acceleration(self) -> float: ...

    @abstractmethod
    def get_state(self) -> str: ...

    @abstractmethod
    def get_state_topic(self) -> str: ...

    def is_healthy(self) -> bool:
        """Healthy = robot is not in error state."""
        return self.get_state() not in ("error", "disconnected", "fault")

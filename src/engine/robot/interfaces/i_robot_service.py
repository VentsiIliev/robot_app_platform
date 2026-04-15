from abc import ABC, abstractmethod
from typing import Optional
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

    @abstractmethod
    def execute_trajectory(
        self,
        path,
        rx: float = 180,
        ry: float = 0,
        rz: float = 0,
        vel: float = 0.1,
        acc: float = 0.1,
        blocking: bool = False,
        orientation_mode: str = "constant",
    ):
        ...

    def get_execution_status(self):
        return None

    def get_last_trajectory_command_info(self):
        return None

    def unwind_joint6(
        self,
        blocking: bool = True,
        queue_if_busy: bool = True,
        vel: float | None = None,
        acc: float | None = None,
    ) -> bool:
        return False

    @abstractmethod
    def enable_safety_walls(self) -> bool: ...

    @abstractmethod
    def disable_safety_walls(self) -> bool: ...

    @abstractmethod
    def are_safety_walls_enabled(self) -> Optional[bool]: ...

    @abstractmethod
    def get_safety_walls_status(self) -> dict: ...

    @abstractmethod
    def validate_pose(
        self,
        start_position,
        target_position,
        tool: int = 0,
        user: int = 0,
        start_joint_state: dict | None = None,
    ) -> dict: ...

    def is_healthy(self) -> bool:
        """Healthy = robot is not in error state."""
        return self.get_state() not in ("error", "disconnected", "fault")

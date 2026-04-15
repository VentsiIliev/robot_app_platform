from abc import ABC, abstractmethod
from typing import List

from ..enums.axis import RobotAxis, Direction


class IRobot(ABC):

    @abstractmethod
    def move_ptp(
        self,
        position: List[float],
        tool: int,
        user: int,
        vel: float,
        acc: float,
        blocking: bool = True,
    ) -> int:
        """Point-to-point motion (fastest path). Returns 0 on success."""
        ...

    @abstractmethod
    def move_linear(
        self,
        position: List[float],
        tool: int,
        user: int,
        vel: float,
        acc: float,
        blend_radius: float = 0.0,
        blocking: bool = True,
    ) -> int:
        """Straight-line TCP motion. Returns 0 on success."""
        ...

    @abstractmethod
    def start_jog(
        self,
        axis: RobotAxis,
        direction: Direction,
        step: float,
        vel: float,
        acc: float,
    ) -> int:
        ...

    @abstractmethod
    def stop_motion(self) -> int:
        ...

    @abstractmethod
    def get_current_position(self) -> List[float]:
        ...

    @abstractmethod
    def get_current_velocity(self) -> float:
        ...

    @abstractmethod
    def get_current_acceleration(self) -> float:
        ...

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
    ) -> None:
        ...

    @abstractmethod
    def enable(self) -> None:
        ...

    @abstractmethod
    def disable(self) -> None:
        ...

    def clone(self) -> 'IRobot':
        """Return a new independent connection to the same robot endpoint.
        Default: returns self (safe for stateless/HTTP transports).
        Override in drivers that hold exclusive connections (e.g. TCP SDK).
        """
        return self

    def get_execution_status(self):
        """Optional execution/queue status from the underlying robot bridge."""
        return None

    def get_last_trajectory_command_info(self):
        """Optional metadata about the last submitted trajectory command."""
        return None

    def unwind_joint6(
        self,
        blocking: bool = True,
        queue_if_busy: bool = True,
        vel: float | None = None,
        acc: float | None = None,
    ) -> int:
        """Optional explicit Joint_6 unwind."""
        return -1

    def get_connection_state(self) -> str:
        """Optional lifecycle/availability state for the underlying transport."""
        return "idle"

    def get_connection_details(self) -> dict:
        """Optional diagnostic details about the underlying transport state."""
        return {}

    def enable_safety_walls(self) -> bool:
        """Optional remote safety-wall control."""
        return False

    def disable_safety_walls(self) -> bool:
        """Optional remote safety-wall control."""
        return False

    def are_safety_walls_enabled(self):
        """Optional remote safety-wall status."""
        status = self.get_safety_walls_status()
        return status.get("enabled") if isinstance(status, dict) else None

    def get_safety_walls_status(self) -> dict:
        """Optional remote safety-wall status payload."""
        return {"supported": False, "enabled": None}

    def validate_pose(
        self,
        start_position: List[float],
        target_position: List[float],
        tool: int = 0,
        user: int = 0,
        start_joint_state: dict | None = None,
    ) -> dict:
        """Optional remote pose reachability validation."""
        return {"supported": False, "reachable": False}

    def prefers_incremental_jog(self) -> bool:
        """Whether jog should prefer the robot's native incremental jog API over synthesized move commands."""
        return False

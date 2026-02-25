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
    def enable(self) -> None:
        ...

    @abstractmethod
    def disable(self) -> None:
        ...

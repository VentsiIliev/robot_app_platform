from abc import ABC, abstractmethod
from typing import List
from ..enums import axis


class IMotionService(ABC):
    """Low-level motion control interface."""

    @abstractmethod
    def move_ptp(
        self,
        position: List[float],
        tool: int,
        user: int,
        velocity: float,
        acceleration: float,
        wait_to_reach: bool = False
    ) -> bool:
        """
        Point-to-point motion (joint/cartesian PTP).
        Fastest path, not guaranteed straight TCP path.
        """
        ...

    @abstractmethod
    def move_linear(
        self,
        position: List[float],
        tool: int,
        user: int,
        velocity: float,
        acceleration: float,
        blendR: float,
        wait_to_reach: bool = False
    ) -> bool:
        """
        Linear TCP motion (straight-line in Cartesian space).
        """
        ...

    @abstractmethod
    def start_jog(
        self,
        axis: axis.RobotAxis,
        direction: axis.Direction,
        step: float
    ) -> int:
        ...

    @abstractmethod
    def stop_motion(self) -> bool:
        ...

    @abstractmethod
    def get_current_position(self) -> List[float]:
        ...
from abc import ABC, abstractmethod
from typing import Callable, List
from ..enums import axis
from ..motion_sequence import MotionSequenceSegment


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
        wait_to_reach: bool = False,
        wait_cancelled: Callable[[], bool] | None = None,
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
        wait_to_reach: bool = False,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        """
        Linear TCP motion (straight-line in Cartesian space).
        """
        ...

    @abstractmethod
    def move_sequence(
        self,
        segments: List[MotionSequenceSegment],
        tool: int,
        user: int,
        wait_to_reach: bool = False,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        """Execute an ordered sequence of explicitly parameterized motion segments."""
        ...

    @abstractmethod
    def move_custom_sequence(
        self,
        segments: List[MotionSequenceSegment],
        tool: int,
        user: int,
        wait_to_reach: bool = False,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        """Execute a custom queued sequence of explicitly parameterized motion segments."""
        ...

    @abstractmethod
    def start_jog(
        self,
        axis: axis.RobotAxis,
        direction: axis.Direction,
        step: float,
        velocity: float | None = None,
        acceleration: float | None = None,
    ) -> int:
        ...

    @abstractmethod
    def stop_motion(self) -> bool:
        ...

    @abstractmethod
    def get_current_position(self) -> List[float]:
        ...

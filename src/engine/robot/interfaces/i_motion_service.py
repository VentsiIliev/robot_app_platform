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
        allow_subzero_step_recovery: bool = False,
        allow_collision_recovery: bool = False,
        bypass_safety_limits: bool = False,
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

    def start_servo_jog(
        self,
        axis: axis.RobotAxis,
        direction: axis.Direction,
        linear_mm_s: float | None = None,
        angular_deg_s: float | None = None,
        *,
        frame: str | int = "user",
        tool: int = 0,
        user: int = 0,
        allow_subzero_descent: bool = False,
        allow_subzero_retract_settle: bool = False,
        disable_collision_checking: bool = False,
    ) -> int:
        return -1

    def start_joint_jog(
        self,
        joint: str,
        direction: axis.Direction,
        step: float,
        velocity: float | None = None,
        acceleration: float | None = None,
    ) -> int:
        return -1

    def stop_servo_jog(self, *, restore_collision_checking: bool = True) -> int:
        return -1

    def servo_jog_to_z(self, **kwargs) -> dict | None:
        return None

    def move_fast_linear(self, **kwargs) -> dict | None:
        """Optionally execute a blocking Pilz LIN move and return its final outcome."""
        return None

    @abstractmethod
    def stop_motion(self) -> bool:
        ...

    @abstractmethod
    def get_current_position(self) -> List[float]:
        ...

    def get_current_position_fresh(self) -> List[float]:
        """Return a fresh pose when a safety-critical motion loop requires it."""
        return self.get_current_position()

    def register_motion_corridor(self, corridor) -> None:
        """Register one installation-specific constrained passage."""
        raise NotImplementedError

    def set_motion_passage_closed(self, passage_id: str, closed: bool) -> bool:
        """Add or remove a configured planning-scene passage lid."""
        return False

    def move_linear_in_corridor(
        self,
        corridor_id: str,
        position: List[float],
        tool: int,
        user: int,
        velocity: float,
        acceleration: float,
        blendR: float = 0.0,
        wait_to_reach: bool = False,
    ) -> bool:
        """Execute a bounded LIN move that may cross the platform Z=0 floor."""
        return False

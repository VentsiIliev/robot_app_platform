from dataclasses import dataclass


@dataclass(frozen=True)
class EndEffectorPoint:
    """A named physical point on the robot end-effector.

    ``offset_x`` and ``offset_y`` are the measured offset from the camera
    center to this point, expressed in the local robot wrist frame (mm).
    The camera center itself has zero offsets.
    """
    name: str
    offset_x: float = 0.0
    offset_y: float = 0.0

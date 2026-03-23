from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisionPoseRequest:
    """Describe the pose you want, using image pixels for XY and robot units for Z/RX/RY/RZ.

    Simple mental model:
    - ``x_pixels`` / ``y_pixels`` say which image point should be targeted
    - ``z_mm`` says the base robot Z height you want
    - ``rx_degrees`` / ``ry_degrees`` / ``rz_degrees`` say the final tool orientation

    ``VisionTargetResolver`` takes this request, applies all XY targeting math
    (homography, plane mapping, TCP delta, end-effector point offset) and then
    adds any frame height correction on top of ``z_mm`` to produce the final
    robot pose.
    """

    x_pixels: float
    y_pixels: float
    z_mm: float
    rz_degrees: float
    rx_degrees: float
    ry_degrees: float

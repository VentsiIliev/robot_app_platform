from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PixelTarget:
    """An image-space detection point with the full robot tool orientation at capture time.

    ``px`` and ``py`` are pixel coordinates in the camera image.
    ``rz`` is the robot wrist Z-rotation in degrees — drives both the
    camera-to-TCP delta correction and the end-effector offset rotation.
    Pass ``None`` to skip TCP-delta correction (e.g. camera-center targets
    where orientation-dependent correction is not wanted).
    ``rx`` and ``ry`` are the tool tip orientation angles (typically fixed
    per application, e.g. ``rx=180, ry=0`` for a downward-facing tool).

    Together with a ``TargetTransformResult``, a ``PixelTarget`` provides
    everything needed to build a complete ``[x, y, z, rx, ry, rz]`` robot pose.
    """
    px: float
    py: float
    rz: float
    rx: float
    ry: float

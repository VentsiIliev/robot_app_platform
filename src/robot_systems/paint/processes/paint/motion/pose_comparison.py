"""Pose comparison helpers shared by paint motion workflows."""

from __future__ import annotations

from src.engine.geometry.planar import unwrap_degrees


def poses_close(
    left: list[float] | None,
    right: list[float] | None,
    tolerance: float = 1e-3,
) -> bool:
    """Return whether two six-axis poses match, accounting for wrapped RZ angles."""
    if left is None or right is None or len(left) < 6 or len(right) < 6:
        return False
    if not all(abs(float(a) - float(b)) <= tolerance for a, b in zip(left[:5], right[:5])):
        return False
    equivalent_rz = unwrap_degrees(float(right[5]), float(left[5]))
    return abs(equivalent_rz - float(right[5])) <= tolerance

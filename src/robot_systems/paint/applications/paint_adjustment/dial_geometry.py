from __future__ import annotations


def dial_angle_for_value(
    value: int,
    minimum: int,
    spacing: int,
    count: int,
) -> float | None:
    """Map a register value to a clockwise dial angle; setting 1 is at top."""
    if spacing < 1 or count < 1:
        raise ValueError("Dial calibration must have positive spacing and count")
    maximum = minimum + spacing * (count - 1)
    if not minimum <= value <= maximum:
        return None
    if count == 1:
        return -90.0
    return -90.0 + ((maximum - value) / spacing) * (360.0 / count)

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


def dial_value_for_angle(angle: float, minimum: int, spacing: int, count: int) -> int:
    """Map a pointer angle to a register value, clamping the gap after the last setting."""
    if spacing < 1 or count < 1:
        raise ValueError("Dial calibration must have positive spacing and count")
    if count == 1:
        return minimum
    offset = (angle + 90.0) % 360.0
    active_arc = 360.0 * (count - 1) / count
    if offset > active_arc:
        if offset - active_arc < (360.0 - active_arc) / 2:
            return minimum
        return minimum + spacing * (count - 1)
    maximum = minimum + spacing * (count - 1)
    return round(maximum - offset * spacing * count / 360.0)


def dial_setting_for_value(
    value: int, minimum: int, spacing: int, count: int
) -> float | None:
    """Express a register value on the numbered setting scale."""
    if spacing < 1 or count < 1:
        raise ValueError("Dial calibration must have positive spacing and count")
    maximum = minimum + spacing * (count - 1)
    if not minimum <= value <= maximum:
        return None
    return 1.0 + (maximum - value) / spacing

from __future__ import annotations

import math


def rotate_xy(x: float, y: float, angle_degrees: float) -> tuple[float, float]:
    angle_rad = math.radians(float(angle_degrees))
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return x * cos_a - y * sin_a, x * sin_a + y * cos_a


def rotate_xy_about(
    point_xy: tuple[float, float],
    angle_degrees: float,
    pivot_xy: tuple[float, float],
) -> tuple[float, float]:
    px, py = float(point_xy[0]), float(point_xy[1])
    ox, oy = float(pivot_xy[0]), float(pivot_xy[1])
    dx = px - ox
    dy = py - oy
    rx, ry = rotate_xy(dx, dy, angle_degrees)
    return ox + rx, oy + ry


def unwrap_degrees(previous: float, current: float) -> float:
    value = float(current)
    prev = float(previous)
    while value - prev > 180.0:
        value -= 360.0
    while value - prev < -180.0:
        value += 360.0
    return value


def normalize_degrees(angle: float) -> float:
    value = float(angle)
    while value > 180.0:
        value -= 360.0
    while value <= -180.0:
        value += 360.0
    return value


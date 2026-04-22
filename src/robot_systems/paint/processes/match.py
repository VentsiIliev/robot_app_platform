import numpy as np

# TODO SURE I HAVE UTILS THAT COVER THIS!
def _rotate_xy_about(point_xy: tuple[float, float], angle_degrees: float, pivot_xy: tuple[float, float]) -> tuple[float, float]:
    angle_rad = float(np.radians(angle_degrees))
    cos_a = float(np.cos(angle_rad))
    sin_a = float(np.sin(angle_rad))
    px, py = float(point_xy[0]), float(point_xy[1])
    ox, oy = float(pivot_xy[0]), float(pivot_xy[1])
    dx = px - ox
    dy = py - oy
    return (
        ox + cos_a * dx - sin_a * dy,
        oy + sin_a * dx + cos_a * dy,
    )

def _rotate_xy(x: float, y: float, angle_degrees: float) -> tuple[float, float]:
    angle_rad = float(np.radians(angle_degrees))
    cos_a = float(np.cos(angle_rad))
    sin_a = float(np.sin(angle_rad))
    return (
        x * cos_a - y * sin_a,
        x * sin_a + y * cos_a,
    )

def _unwrap_degrees(previous: float, current: float) -> float:
    value = float(current)
    prev = float(previous)
    while value - prev > 180.0:
        value -= 360.0
    while value - prev < -180.0:
        value += 360.0
    return value

def _normalize_degrees(angle: float) -> float:
    value = float(angle)
    while value > 180.0:
        value -= 360.0
    while value <= -180.0:
        value += 360.0
    return value
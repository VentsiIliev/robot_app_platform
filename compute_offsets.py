import math
from typing import Tuple


# ============================================================
# 1. INPUT: measured positions at SAME physical point (rz=0)
# ============================================================

camera_center = (-78.185, 390.527)
tool_point = (-82.573, 466.438)
gripper_point = (16.656, 469.511)


# ============================================================
# 2. OFFSET COMPUTATION
# ============================================================

def compute_offset(from_point: Tuple[float, float],
                   to_point: Tuple[float, float]) -> Tuple[float, float]:
    """
    Compute offset vector: to_point - from_point
    """
    return (to_point[0] - from_point[0],
            to_point[1] - from_point[1])


camera_to_gripper = compute_offset(camera_center, gripper_point)
camera_to_tool = compute_offset(camera_center, tool_point)


# ============================================================
# 3. ROTATION FUNCTION
# ============================================================

def rotate_xy(offset: Tuple[float, float], rz_deg: float) -> Tuple[float, float]:
    """
    Rotate XY offset by rz (degrees)
    """
    x, y = offset
    angle = math.radians(rz_deg)

    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    x_rot = x * cos_a - y * sin_a
    y_rot = x * sin_a + y * cos_a

    return x_rot, y_rot


# ============================================================
# 4. APPLY OFFSET FUNCTIONS
# ============================================================

def apply_gripper_offset(
    tcp_xy: Tuple[float, float],
    rz_deg: float
) -> Tuple[float, float]:
    """
    Convert camera-aligned TCP → gripper-aligned TCP
    """
    dx_rot, dy_rot = rotate_xy(camera_to_gripper, rz_deg)

    return (
        tcp_xy[0] + dx_rot,
        tcp_xy[1] + dy_rot
    )


def apply_tool_offset(
    tcp_xy: Tuple[float, float],
    rz_deg: float
) -> Tuple[float, float]:
    """
    Convert camera-aligned TCP → tool-aligned TCP
    """
    dx_rot, dy_rot = rotate_xy(camera_to_tool, rz_deg)

    return (
        tcp_xy[0] + dx_rot,
        tcp_xy[1] + dy_rot
    )


# ============================================================
# 5. DEBUG / VALIDATION
# ============================================================

def print_offsets():
    print("Camera → Gripper offset:", camera_to_gripper)
    print("Camera → Tool offset:", camera_to_tool)


def ttest_example():
    """
    Your real example:
    camera already aligned → compute gripper position
    """
    tcp_camera = (-315.73, -75.558)
    rz = 52.19

    tcp_gripper = apply_gripper_offset(tcp_camera, rz)
    tcp_tool = apply_tool_offset(tcp_camera, rz)

    print("\n--- TEST ---")
    print("Camera-aligned TCP:", tcp_camera)
    print("Gripper-aligned TCP:", tcp_gripper)
    print("Tool-aligned TCP:", tcp_tool)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    print_offsets()
    ttest_example()
#!/usr/bin/env python3

import json
import math
import numpy as np


# =========================
# CONFIG — EDIT THESE
# =========================

JSON_FILE = "/home/ilv/Desktop/robot_app_platform/scripts/example_tcp_calib_samples.json"

PARENT_FRAME = "tool0"
CHILD_FRAME = "tool_tcp"

# Use:
#   "rpy"    -> rx, ry, rz are roll, pitch, yaw in degrees
#   "rotvec" -> rx, ry, rz are axis-angle rotation-vector values in degrees
ROTATION_FORMAT = "rpy"


# =========================
# ROTATION CONVERSIONS
# =========================

def rpy_deg_to_rot(rx_deg, ry_deg, rz_deg):
    """
    Convert roll, pitch, yaw in degrees to a rotation matrix.

    Convention:
      R = Rz(yaw) @ Ry(pitch) @ Rx(roll)

    This matches the usual URDF fixed-axis rpy convention.
    """

    roll = math.radians(rx_deg)
    pitch = math.radians(ry_deg)
    yaw = math.radians(rz_deg)

    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)

    Rx = np.array([
        [1.0, 0.0, 0.0],
        [0.0, cr, -sr],
        [0.0, sr, cr],
    ])

    Ry = np.array([
        [cp, 0.0, sp],
        [0.0, 1.0, 0.0],
        [-sp, 0.0, cp],
    ])

    Rz = np.array([
        [cy, -sy, 0.0],
        [sy, cy, 0.0],
        [0.0, 0.0, 1.0],
    ])

    return Rz @ Ry @ Rx


def rotvec_deg_to_rot(rx_deg, ry_deg, rz_deg):
    """
    Convert rotation vector in degrees to a rotation matrix.

    The vector direction is the rotation axis.
    The vector magnitude is the rotation angle in degrees.
    """

    r = np.array([rx_deg, ry_deg, rz_deg], dtype=float)
    theta_deg = np.linalg.norm(r)

    if theta_deg < 1e-12:
        return np.eye(3)

    axis = r / theta_deg
    theta = math.radians(theta_deg)

    x, y, z = axis

    K = np.array([
        [0.0, -z, y],
        [z, 0.0, -x],
        [-y, x, 0.0],
    ])

    return np.eye(3) + math.sin(theta) * K + (1.0 - math.cos(theta)) * (K @ K)


# =========================
# JSON READING
# =========================

def read_samples_json(path):
    """
    JSON format:

    [
      {"x": 412.1, "y": 103.2, "z": 522.4, "rx": 12.0, "ry": -43.0, "rz": 91.0},
      ...
    ]

    x, y, z are in millimeters.
    rx, ry, rz are in degrees.
    """

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON root must be a list of samples")

    samples = []

    required = {"x", "y", "z", "rx", "ry", "rz"}

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Sample {i} must be an object")

        missing = required - set(item.keys())
        if missing:
            raise ValueError(f"Sample {i} is missing fields: {sorted(missing)}")

        samples.append({
            "x_mm": float(item["x"]),
            "y_mm": float(item["y"]),
            "z_mm": float(item["z"]),
            "rx_deg": float(item["rx"]),
            "ry_deg": float(item["ry"]),
            "rz_deg": float(item["rz"]),
        })

    return samples


# =========================
# TCP SOLVER
# =========================

def solve_tcp(samples, rotation_format):
    """
    Each sample must be the transform:

      base -> tool0

    The math solves:

      R_i * tcp_in_tool0 + p_i = fixed_touch_point

    Unknowns:

      tcp_in_tool0
      fixed_touch_point
    """

    if len(samples) < 4:
        print("WARNING: Use at least 4 samples. Prefer 8–15 samples.")

    A_blocks = []
    b_blocks = []
    parsed = []

    for s in samples:
        # Convert position from mm to meters
        p = np.array([
            s["x_mm"] / 1000.0,
            s["y_mm"] / 1000.0,
            s["z_mm"] / 1000.0,
        ])

        if rotation_format == "rpy":
            R = rpy_deg_to_rot(
                s["rx_deg"],
                s["ry_deg"],
                s["rz_deg"],
            )
        elif rotation_format == "rotvec":
            R = rotvec_deg_to_rot(
                s["rx_deg"],
                s["ry_deg"],
                s["rz_deg"],
            )
        else:
            raise ValueError(
                "ROTATION_FORMAT must be either 'rpy' or 'rotvec'"
            )

        # R * tcp - touch_point = -p
        A_i = np.hstack([R, -np.eye(3)])
        b_i = -p

        A_blocks.append(A_i)
        b_blocks.append(b_i)
        parsed.append((R, p))

    A = np.vstack(A_blocks)
    b = np.hstack(b_blocks)

    solution, *_ = np.linalg.lstsq(A, b, rcond=None)

    tcp_in_tool0 = solution[0:3]
    touch_point_in_base = solution[3:6]

    errors = []

    for R, p in parsed:
        predicted_tip = R @ tcp_in_tool0 + p
        error = predicted_tip - touch_point_in_base
        errors.append(np.linalg.norm(error))

    errors = np.array(errors)

    return {
        "tcp_m": tcp_in_tool0,
        "touch_m": touch_point_in_base,
        "rms_m": float(np.sqrt(np.mean(errors ** 2))),
        "mean_m": float(np.mean(errors)),
        "max_m": float(np.max(errors)),
        "rank": int(np.linalg.matrix_rank(A)),
        "condition": float(np.linalg.cond(A)),
    }


# =========================
# OUTPUT
# =========================

def print_result(result):
    tcp_m = result["tcp_m"]
    tcp_mm = tcp_m * 1000.0

    print()
    print("========== TCP CALIBRATION RESULT ==========")
    print()
    print(f"TCP offset in {PARENT_FRAME}:")
    print(f"  x = {tcp_mm[0]: .3f} mm")
    print(f"  y = {tcp_mm[1]: .3f} mm")
    print(f"  z = {tcp_mm[2]: .3f} mm")

    print()
    print("Same offset in meters:")
    print(f"  x = {tcp_m[0]: .9f} m")
    print(f"  y = {tcp_m[1]: .9f} m")
    print(f"  z = {tcp_m[2]: .9f} m")

    print()
    print("Calibration error:")
    print(f"  RMS  = {result['rms_m'] * 1000.0:.3f} mm")
    print(f"  Mean = {result['mean_m'] * 1000.0:.3f} mm")
    print(f"  Max  = {result['max_m'] * 1000.0:.3f} mm")

    print()
    print("Numerics:")
    print(f"  Rank      = {result['rank']} / 6")
    print(f"  Condition = {result['condition']:.3e}")

    if result["rank"] < 6:
        print()
        print("WARNING: Under-constrained calibration.")
        print("Use more poses with larger orientation differences.")

    if result["condition"] > 1e6:
        print()
        print("WARNING: Poor pose geometry.")
        print("Your samples may be too similar.")

    print()
    print("URDF / Xacro:")
    print()
    print(f'<link name="{CHILD_FRAME}"/>')
    print()
    print(f'<joint name="{PARENT_FRAME}_to_{CHILD_FRAME}" type="fixed">')
    print(f'  <parent link="{PARENT_FRAME}"/>')
    print(f'  <child link="{CHILD_FRAME}"/>')
    print(
        f'  <origin xyz="{tcp_m[0]:.9f} {tcp_m[1]:.9f} {tcp_m[2]:.9f}" '
        f'rpy="0 0 0"/>'
    )
    print("</joint>")

    print()
    print("ROS 2 static transform test:")
    print()
    print(
        "ros2 run tf2_ros static_transform_publisher "
        f"--x {tcp_m[0]:.9f} "
        f"--y {tcp_m[1]:.9f} "
        f"--z {tcp_m[2]:.9f} "
        "--roll 0 --pitch 0 --yaw 0 "
        f"--frame-id {PARENT_FRAME} "
        f"--child-frame-id {CHILD_FRAME}"
    )
    print()


# =========================
# MAIN
# =========================

def main():
    samples = read_samples_json(JSON_FILE)
    result = solve_tcp(samples, ROTATION_FORMAT)
    print_result(result)


if __name__ == "__main__":
    main()
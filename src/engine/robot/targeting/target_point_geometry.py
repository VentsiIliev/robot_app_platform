from __future__ import annotations

import math
from typing import Sequence, Tuple

from src.engine.geometry.planar import rotate_xy


def rotate_offset_xy(offset_x: float, offset_y: float, rz_degrees: float) -> Tuple[float, float]:
    """Rotate a local target-point offset into robot XY for the given wrist angle."""
    return rotate_xy(float(offset_x), float(offset_y), float(rz_degrees))


def rotate_offset_xyz(
    offset_x: float,
    offset_y: float,
    offset_z: float = 0.0,
    *,
    rx_degrees: float,
    ry_degrees: float,
    rz_degrees: float,
) -> Tuple[float, float, float]:
    """Rotate a local target-point offset into robot XYZ for the given tool orientation."""
    x = float(offset_x)
    y = float(offset_y)
    z = float(offset_z)
    rx = math.radians(float(rx_degrees))
    ry = math.radians(float(ry_degrees))
    rz = math.radians(float(rz_degrees))
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    return (
        (cy * cz * x)
        + ((cz * sx * sy - cx * sz) * y)
        + ((cx * cz * sy + sx * sz) * z),
        (cy * sz * x)
        + ((cx * cz + sx * sy * sz) * y)
        + ((cx * sy * sz - cz * sx) * z),
        (-sy * x) + (cy * sx * y) + (cx * cy * z),
    )


def _flat_rz_compatible(rx_degrees: float, ry_degrees: float) -> bool:
    """Return True when legacy XY/RZ targeting is the better compatibility model."""
    rx = abs(abs(float(rx_degrees)) - 180.0)
    ry = abs(float(ry_degrees))
    return rx <= 45.0 and ry <= 45.0


def _orientation3(values: Sequence[float] | None, fallback_rz: float = 0.0) -> tuple[float, float, float]:
    if values is None:
        return 0.0, 0.0, float(fallback_rz)
    if len(values) >= 3:
        return float(values[0]), float(values[1]), float(values[2])
    if len(values) == 2:
        return float(values[0]), float(values[1]), float(fallback_rz)
    if len(values) == 1:
        return 0.0, 0.0, float(values[0])
    return 0.0, 0.0, float(fallback_rz)


def tcp_delta_xyz(
    camera_to_tcp_x_offset: float,
    camera_to_tcp_y_offset: float,
    *,
    current_orientation: Sequence[float],
    reference_orientation: Sequence[float] | None = None,
) -> Tuple[float, float, float]:
    """Return the camera-to-TCP sweep delta between two full tool orientations."""
    tcp_x = float(camera_to_tcp_x_offset)
    tcp_y = float(camera_to_tcp_y_offset)
    if tcp_x == 0.0 and tcp_y == 0.0:
        return 0.0, 0.0, 0.0
    rx, ry, rz = _orientation3(current_orientation)
    ref_rx, ref_ry, ref_rz = _orientation3(reference_orientation, fallback_rz=0.0)
    if _flat_rz_compatible(rx, ry) and _flat_rz_compatible(ref_rx, ref_ry):
        dx, dy = tcp_delta_xy(tcp_x, tcp_y, rz, ref_rz)
        return dx, dy, 0.0
    cur = rotate_offset_xyz(tcp_x, tcp_y, 0.0, rx_degrees=rx, ry_degrees=ry, rz_degrees=rz)
    ref = rotate_offset_xyz(tcp_x, tcp_y, 0.0, rx_degrees=ref_rx, ry_degrees=ref_ry, rz_degrees=ref_rz)
    return cur[0] - ref[0], cur[1] - ref[1], cur[2] - ref[2]


def selected_xyz_from_command_xyz(
    command_x: float,
    command_y: float,
    command_z: float,
    *,
    orientation: Sequence[float],
    point_offset_x: float = 0.0,
    point_offset_y: float = 0.0,
    camera_to_tcp_x_offset: float = 0.0,
    camera_to_tcp_y_offset: float = 0.0,
    reference_orientation: Sequence[float] | None = None,
) -> Tuple[float, float, float]:
    """Convert commanded robot XYZ into selected-point XYZ on the work plane."""
    rx, ry, rz = _orientation3(orientation)
    ref_rx, ref_ry, _ = _orientation3(reference_orientation, fallback_rz=0.0)
    tcp_dx, tcp_dy, tcp_dz = tcp_delta_xyz(
        camera_to_tcp_x_offset,
        camera_to_tcp_y_offset,
        current_orientation=(rx, ry, rz),
        reference_orientation=reference_orientation,
    )
    if _flat_rz_compatible(rx, ry) and _flat_rz_compatible(ref_rx, ref_ry):
        point_dx, point_dy = rotate_offset_xy(point_offset_x, point_offset_y, rz)
        point_dz = 0.0
    else:
        point_dx, point_dy, point_dz = rotate_offset_xyz(
            point_offset_x,
            point_offset_y,
            0.0,
            rx_degrees=rx,
            ry_degrees=ry,
            rz_degrees=rz,
        )
    return (
        float(command_x) + tcp_dx - point_dx,
        float(command_y) + tcp_dy - point_dy,
        float(command_z) + tcp_dz - point_dz,
    )


def command_xyz_from_selected_xyz(
    selected_x: float,
    selected_y: float,
    selected_z: float,
    *,
    orientation: Sequence[float],
    point_offset_x: float = 0.0,
    point_offset_y: float = 0.0,
    camera_to_tcp_x_offset: float = 0.0,
    camera_to_tcp_y_offset: float = 0.0,
    reference_orientation: Sequence[float] | None = None,
) -> Tuple[float, float, float]:
    """Convert selected-point XYZ on the work plane into commanded robot XYZ."""
    rx, ry, rz = _orientation3(orientation)
    ref_rx, ref_ry, _ = _orientation3(reference_orientation, fallback_rz=0.0)
    tcp_dx, tcp_dy, tcp_dz = tcp_delta_xyz(
        camera_to_tcp_x_offset,
        camera_to_tcp_y_offset,
        current_orientation=(rx, ry, rz),
        reference_orientation=reference_orientation,
    )
    if _flat_rz_compatible(rx, ry) and _flat_rz_compatible(ref_rx, ref_ry):
        point_dx, point_dy = rotate_offset_xy(point_offset_x, point_offset_y, rz)
        point_dz = 0.0
    else:
        point_dx, point_dy, point_dz = rotate_offset_xyz(
            point_offset_x,
            point_offset_y,
            0.0,
            rx_degrees=rx,
            ry_degrees=ry,
            rz_degrees=rz,
        )
    return (
        float(selected_x) - tcp_dx + point_dx,
        float(selected_y) - tcp_dy + point_dy,
        float(selected_z) - tcp_dz + point_dz,
    )


def tcp_delta_xy(
    camera_to_tcp_x_offset: float,
    camera_to_tcp_y_offset: float,
    current_rz: float,
    reference_rz: float = 0.0,
) -> Tuple[float, float]:
    """Return the camera-to-TCP sweep delta between reference and current wrist angles."""
    tcp_x = float(camera_to_tcp_x_offset)
    tcp_y = float(camera_to_tcp_y_offset)
    if tcp_x == 0.0 and tcp_y == 0.0:
        return 0.0, 0.0
    cur_x, cur_y = rotate_offset_xy(tcp_x, tcp_y, current_rz)
    ref_x, ref_y = rotate_offset_xy(tcp_x, tcp_y, reference_rz)
    return cur_x - ref_x, cur_y - ref_y


def selected_xy_from_command_xy(
    command_x: float,
    command_y: float,
    rz_degrees: float,
    point_offset_x: float = 0.0,
    point_offset_y: float = 0.0,
    camera_to_tcp_x_offset: float = 0.0,
    camera_to_tcp_y_offset: float = 0.0,
    reference_rz: float = 0.0,
) -> Tuple[float, float]:
    """Convert commanded robot XY into selected-point XY on the work plane."""
    tcp_dx, tcp_dy = tcp_delta_xy(
        camera_to_tcp_x_offset,
        camera_to_tcp_y_offset,
        rz_degrees,
        reference_rz,
    )
    point_dx, point_dy = rotate_offset_xy(point_offset_x, point_offset_y, rz_degrees)
    return float(command_x) + tcp_dx - point_dx, float(command_y) + tcp_dy - point_dy


def command_xy_from_selected_xy(
    selected_x: float,
    selected_y: float,
    rz_degrees: float,
    point_offset_x: float = 0.0,
    point_offset_y: float = 0.0,
    camera_to_tcp_x_offset: float = 0.0,
    camera_to_tcp_y_offset: float = 0.0,
    reference_rz: float = 0.0,
) -> Tuple[float, float]:
    """Convert selected-point XY on the work plane into commanded robot XY."""
    tcp_dx, tcp_dy = tcp_delta_xy(
        camera_to_tcp_x_offset,
        camera_to_tcp_y_offset,
        rz_degrees,
        reference_rz,
    )
    point_dx, point_dy = rotate_offset_xy(point_offset_x, point_offset_y, rz_degrees)
    return float(selected_x) - tcp_dx + point_dx, float(selected_y) - tcp_dy + point_dy

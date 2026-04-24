from __future__ import annotations

from typing import Tuple

from src.engine.geometry.planar import rotate_xy


def rotate_offset_xy(offset_x: float, offset_y: float, rz_degrees: float) -> Tuple[float, float]:
    """Rotate a local target-point offset into robot XY for the given wrist angle."""
    return rotate_xy(float(offset_x), float(offset_y), float(rz_degrees))


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

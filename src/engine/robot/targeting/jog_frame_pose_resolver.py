from __future__ import annotations

import math
from typing import Callable, Optional, Sequence

from src.engine.robot.targeting.end_effector_point import EndEffectorPoint
from src.engine.robot.targeting.point_registry import PointRegistry


class JogFramePoseResolver:
    """Resolve incremental jog commands so a selected end-effector point stays consistent."""

    def __init__(
        self,
        registry: PointRegistry,
        camera_to_tcp_x_offset: float = 0.0,
        camera_to_tcp_y_offset: float = 0.0,
        reference_rz_provider: Optional[Callable[[], float]] = None,
    ) -> None:
        self._registry = registry
        self._tcp_x = float(camera_to_tcp_x_offset)
        self._tcp_y = float(camera_to_tcp_y_offset)
        self._reference_rz_provider = reference_rz_provider

    def point_for_name(self, frame_name: str) -> Optional[EndEffectorPoint]:
        try:
            return self._registry.by_name(frame_name)
        except Exception:
            return None

    def available_frames(self) -> list[str]:
        return self._registry.names()

    def resolve(
        self,
        current_pose: Sequence[float],
        axis: str,
        direction: str,
        step: float,
        point: EndEffectorPoint,
    ) -> list[float] | None:
        if len(current_pose) < 6:
            return None

        x, y, z, rx, ry, rz = [float(v) for v in current_pose[:6]]
        axis_name = str(axis).strip().upper()
        sign = 1.0 if str(direction).strip().lower() == "plus" else -1.0
        ref_rz = self._reference_rz()

        selected_x, selected_y = self._selected_xy_from_command(x, y, rz, point.offset_x, point.offset_y, ref_rz)
        target_selected_x = selected_x
        target_selected_y = selected_y
        target_z = z
        target_rx = rx
        target_ry = ry
        target_rz = rz

        if axis_name in {"X", "Y", "Z"}:
            axis_idx = {"X": 0, "Y": 1, "Z": 2}[axis_name]
            dx, dy, dz = _tool_frame_delta([x, y, z, rx, ry, rz], axis_idx, sign, float(step))
            target_selected_x += dx
            target_selected_y += dy
            target_z += dz
        elif axis_name == "RX":
            target_rx += sign * float(step)
        elif axis_name == "RY":
            target_ry += sign * float(step)
        elif axis_name == "RZ":
            target_rz += sign * float(step)
        else:
            return None

        command_x, command_y = self._command_xy_from_selected(
            target_selected_x,
            target_selected_y,
            target_rz,
            point.offset_x,
            point.offset_y,
            ref_rz,
        )
        return [command_x, command_y, target_z, target_rx, target_ry, target_rz]

    def _reference_rz(self) -> float:
        if self._reference_rz_provider is None:
            return 0.0
        try:
            return float(self._reference_rz_provider())
        except Exception:
            return 0.0

    def _selected_xy_from_command(self, command_x: float, command_y: float, rz_degrees: float, point_offset_x: float, point_offset_y: float, reference_rz: float) -> tuple[float, float]:
        tcp_dx, tcp_dy = self._tcp_delta(rz_degrees, reference_rz)
        point_dx, point_dy = _rotate_xy(point_offset_x, point_offset_y, rz_degrees)
        return command_x + tcp_dx - point_dx, command_y + tcp_dy - point_dy

    def _command_xy_from_selected(self, selected_x: float, selected_y: float, rz_degrees: float, point_offset_x: float, point_offset_y: float, reference_rz: float) -> tuple[float, float]:
        tcp_dx, tcp_dy = self._tcp_delta(rz_degrees, reference_rz)
        point_dx, point_dy = _rotate_xy(point_offset_x, point_offset_y, rz_degrees)
        return selected_x - tcp_dx + point_dx, selected_y - tcp_dy + point_dy

    def _tcp_delta(self, current_rz: float, reference_rz: float) -> tuple[float, float]:
        if self._tcp_x == 0.0 and self._tcp_y == 0.0:
            return 0.0, 0.0
        cur_x, cur_y = _rotate_xy(self._tcp_x, self._tcp_y, current_rz)
        ref_x, ref_y = _rotate_xy(self._tcp_x, self._tcp_y, reference_rz)
        return cur_x - ref_x, cur_y - ref_y


def _rotate_xy(x: float, y: float, rz_deg: float) -> tuple[float, float]:
    angle_rad = math.radians(rz_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return x * cos_a - y * sin_a, x * sin_a + y * cos_a


def _tool_frame_delta(position: Sequence[float], axis_idx: int, direction_value: float, step: float) -> tuple[float, float, float]:
    rx_deg = float(position[3])
    ry_deg = float(position[4])
    rz_deg = float(position[5])
    cx, sx = math.cos(math.radians(rx_deg)), math.sin(math.radians(rx_deg))
    cy, sy = math.cos(math.radians(ry_deg)), math.sin(math.radians(ry_deg))
    cz, sz = math.cos(math.radians(rz_deg)), math.sin(math.radians(rz_deg))
    cols = (
        (cy * cz, cy * sz, -sy),
        (cz * sx * sy - cx * sz, cx * cz + sx * sy * sz, cy * sx),
        (cx * cz * sy + sx * sz, cx * sy * sz - cz * sx, cx * cy),
    )
    col = cols[axis_idx]
    scale = direction_value * step
    return col[0] * scale, col[1] * scale, col[2] * scale

from __future__ import annotations

import math
import logging
from typing import Callable, Optional, Sequence

from src.engine.robot.targeting.end_effector_point import EndEffectorPoint
from src.engine.robot.targeting.point_registry import PointRegistry

_logger = logging.getLogger(__name__)


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
        current_tcp_dx, current_tcp_dy = _project_local_xy_to_world_xy(
            self._tcp_x, self._tcp_y, rx, ry, rz
        )
        current_point_dx, current_point_dy = _project_local_xy_to_world_xy(
            point.offset_x, point.offset_y, rx, ry, rz
        )
        selected_x = x - current_tcp_dx + current_point_dx
        selected_y = y - current_tcp_dy + current_point_dy
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

        target_tcp_dx, target_tcp_dy = _project_local_xy_to_world_xy(
            self._tcp_x, self._tcp_y, target_rx, target_ry, target_rz
        )
        target_point_dx, target_point_dy = _project_local_xy_to_world_xy(
            point.offset_x, point.offset_y, target_rx, target_ry, target_rz
        )
        command_x = target_selected_x + target_tcp_dx - target_point_dx
        command_y = target_selected_y + target_tcp_dy - target_point_dy
        _logger.info(
            "[JOG_RESOLVE] frame=%s axis=%s direction=%s step=%s current_pose=(%.3f, %.3f, %.3f, %.3f, %.3f, %.3f) selected_xy=(%.3f, %.3f) current_tcp=(%.3f, %.3f) current_point=(%.3f, %.3f) target_pose=(%.3f, %.3f, %.3f, %.3f, %.3f, %.3f) target_tcp=(%.3f, %.3f) target_point=(%.3f, %.3f)",
            getattr(point, "name", ""),
            axis_name,
            direction,
            step,
            x, y, z, rx, ry, rz,
            selected_x, selected_y,
            current_tcp_dx, current_tcp_dy,
            current_point_dx, current_point_dy,
            command_x, command_y, target_z, target_rx, target_ry, target_rz,
            target_tcp_dx, target_tcp_dy,
            target_point_dx, target_point_dy,
        )
        return [command_x, command_y, target_z, target_rx, target_ry, target_rz]

    def _reference_rz(self) -> float:
        if self._reference_rz_provider is None:
            return 0.0
        try:
            return float(self._reference_rz_provider())
        except Exception:
            return 0.0

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


def _rotation_columns(rx_deg: float, ry_deg: float, rz_deg: float) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    cx, sx = math.cos(math.radians(rx_deg)), math.sin(math.radians(rx_deg))
    cy, sy = math.cos(math.radians(ry_deg)), math.sin(math.radians(ry_deg))
    cz, sz = math.cos(math.radians(rz_deg)), math.sin(math.radians(rz_deg))
    return (
        (cy * cz, cy * sz, -sy),
        (cz * sx * sy - cx * sz, cx * cz + sx * sy * sz, cy * sx),
        (cx * cz * sy + sx * sz, cx * sy * sz - cz * sx, cx * cy),
    )


def _project_local_xy_to_world_xy(
    local_x: float,
    local_y: float,
    rx_deg: float,
    ry_deg: float,
    rz_deg: float,
) -> tuple[float, float]:
    """Project a local in-plane XY offset into robot-world XY for the given wrist orientation."""
    col_x, col_y, _ = _rotation_columns(rx_deg, ry_deg, rz_deg)
    world_x = float(local_x) * col_x[0] + float(local_y) * col_y[0]
    world_y = float(local_x) * col_x[1] + float(local_y) * col_y[1]
    return world_x, world_y

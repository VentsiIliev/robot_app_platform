from __future__ import annotations

import math
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.robot.plane_pose_mapper import PlanePoseMapper
from src.engine.robot.targeting.end_effector_point import EndEffectorPoint
from src.engine.robot.targeting.point_registry import PointRegistry
from src.engine.robot.targeting.target_frame import TargetFrame
from src.engine.robot.targeting.target_point_geometry import (
    command_xy_from_selected_xy,
    rotate_offset_xy,
    tcp_delta_xy,
)
from src.engine.robot.targeting.vision_pose_request import VisionPoseRequest

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TargetTransformResult:
    calibration_xy: Tuple[float, float]
    plane_xy: Tuple[float, float]
    final_xy: Tuple[float, float]
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0
    z: float = 0.0
    pickup_plane_reference_delta_xy: Tuple[float, float] = (0.0, 0.0)
    target_delta_xy: Tuple[float, float] = (0.0, 0.0)
    reference_rz: Optional[float] = None

    def robot_pose(self) -> Tuple[float, float, float, float, float, float]:
        x, y = self.final_xy
        return (x, y, self.z, self.rx, self.ry, self.rz)


class VisionTargetResolver:
    """Resolve an image target into a final robot pose for a chosen end-effector point."""

    def __init__(
        self,
        base_transformer: ICoordinateTransformer,
        registry: PointRegistry,
        camera_to_tcp_x_offset: float = 0.0,
        camera_to_tcp_y_offset: float = 0.0,
        frames: Optional[Dict[str, TargetFrame]] = None,
    ) -> None:
        self._base = base_transformer
        self._registry = registry
        self._tcp_x = float(camera_to_tcp_x_offset)
        self._tcp_y = float(camera_to_tcp_y_offset)
        self._frames: Dict[str, TargetFrame] = frames or {}

    def resolve(
        self,
        target: VisionPoseRequest,
        point: EndEffectorPoint,
        *,
        frame: str = "",
        mapper: Optional[PlanePoseMapper] = None,
    ) -> TargetTransformResult:
        frame_obj = self._frames.get(frame)
        active_mapper = mapper if mapper is not None else (frame_obj.mapper if frame_obj else None)
        current_rz = target.rz_degrees

        _logger.info(
            "[CALIB] Resolve using transformer=%s available=%s frame=%s point=%s tcp_offset=(%.3f, %.3f)",
            self._base.__class__.__name__,
            bool(getattr(self._base, "is_available", lambda: False)()),
            str(frame or ""),
            str(point.name),
            float(self._tcp_x),
            float(self._tcp_y),
        )

        calibration_xy = self._base.transform(target.x_pixels, target.y_pixels)
        plane_xy = _map_plane(calibration_xy, active_mapper)
        # Always apply the TCP-rotation delta so that the camera center lands on
        # the target regardless of the robot's current rz.  The calibration matrix
        # was built at rz≈0; at any other angle the 103 mm camera-to-TCP offset
        # sweeps ~103 mm in the plane, producing a large landing error when the
        # correction is skipped.  Camera points have offset=(0,0) so this path is
        # equivalent to the previous behaviour at rz=0 (delta==0) while being
        # correct for all other angles.
        reference_rz = _reference_rz(active_mapper)
        final_xy = command_xy_from_selected_xy(
            plane_xy[0],
            plane_xy[1],
            current_rz,
            point.offset_x,
            point.offset_y,
            self._tcp_x,
            self._tcp_y,
            reference_rz,
        )
        tcp_delta = tcp_delta_xy(self._tcp_x, self._tcp_y, current_rz, reference_rz)
        if point.offset_x == 0.0 and point.offset_y == 0.0:
            target_delta = (0.0, 0.0)
        else:
            target_delta = rotate_offset_xy(point.offset_x, point.offset_y, current_rz)

        _logger.info(
            "[TARGETING] point=%s frame=%s pixels=(%.3f, %.3f) calibration_xy=(%.3f, %.3f) plane_xy=(%.3f, %.3f) "
            "rz=%.3f reference_rz=%.3f tcp_delta=(%.3f, %.3f) point_offset_local=(%.3f, %.3f) "
            "point_delta_rotated=(%.3f, %.3f) final_xy=(%.3f, %.3f)",
            str(point.name),
            str(frame or ""),
            float(target.x_pixels),
            float(target.y_pixels),
            float(calibration_xy[0]),
            float(calibration_xy[1]),
            float(plane_xy[0]),
            float(plane_xy[1]),
            float(current_rz),
            float(reference_rz),
            float(tcp_delta[0]),
            float(tcp_delta[1]),
            float(point.offset_x),
            float(point.offset_y),
            float(target_delta[0]),
            float(target_delta[1]),
            float(final_xy[0]),
            float(final_xy[1]),
        )

        z_correction = frame_obj.get_z_correction(final_xy[0], final_xy[1]) if frame_obj is not None else 0.0

        return TargetTransformResult(
            calibration_xy=calibration_xy,
            plane_xy=plane_xy,
            final_xy=final_xy,
            rx=target.rx_degrees,
            ry=target.ry_degrees,
            rz=current_rz,
            z=target.z_mm + z_correction,
            pickup_plane_reference_delta_xy=tcp_delta,
            target_delta_xy=target_delta,
            reference_rz=reference_rz,
        )

    @property
    def registry(self) -> PointRegistry:
        return self._registry

    def get_frame(self, name: str) -> Optional[TargetFrame]:
        return self._frames.get(name)

def _map_plane(xy: Tuple[float, float], mapper: Optional[PlanePoseMapper]) -> Tuple[float, float]:
    if mapper is None:
        return xy
    return mapper.map_point(xy[0], xy[1])


def _reference_rz(mapper: Optional[PlanePoseMapper]) -> float:
    if mapper is None:
        return 0.0
    return float(mapper.target_pose.rz)

def _is_camera_point(point: EndEffectorPoint) -> bool:
    return str(point.name).strip().lower() == "camera"

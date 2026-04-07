from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.robot.plane_pose_mapper import PlanePoseMapper
from src.engine.robot.targeting.end_effector_point import EndEffectorPoint
from src.engine.robot.targeting.point_registry import PointRegistry
from src.engine.robot.targeting.target_frame import TargetFrame
from src.engine.robot.targeting.vision_pose_request import VisionPoseRequest


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

        calibration_xy = self._base.transform(target.x_pixels, target.y_pixels)
        plane_xy = _map_plane(calibration_xy, active_mapper)
        # Always apply the TCP-rotation delta so that the camera center lands on
        # the target regardless of the robot's current rz.  The calibration matrix
        # was built at rz≈0; at any other angle the 103 mm camera-to-TCP offset
        # sweeps ~103 mm in the plane, producing a large landing error when the
        # correction is skipped.  Camera points have offset=(0,0) so this path is
        # equivalent to the previous behaviour at rz=0 (delta==0) while being
        # correct for all other angles.
        camera_xy, tcp_delta = self._apply_tcp_delta(plane_xy, current_rz, active_mapper)

        if point.offset_x == 0.0 and point.offset_y == 0.0:
            final_xy = camera_xy
            target_delta = (0.0, 0.0)
        else:
            dx, dy = _rotate_xy(point.offset_x, point.offset_y, current_rz)
            final_xy = (camera_xy[0] + dx, camera_xy[1] + dy)
            target_delta = (dx, dy)

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
            reference_rz=_reference_rz(active_mapper),
        )

    @property
    def registry(self) -> PointRegistry:
        return self._registry

    def get_frame(self, name: str) -> Optional[TargetFrame]:
        return self._frames.get(name)

    def _apply_tcp_delta(self, plane_xy: Tuple[float, float], current_rz: float, active_mapper: Optional[PlanePoseMapper]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        if self._tcp_x == 0.0 and self._tcp_y == 0.0:
            return plane_xy, (0.0, 0.0)

        ref_rz = _reference_rz(active_mapper)
        cur_x, cur_y = _rotate_xy(self._tcp_x, self._tcp_y, current_rz)
        ref_x, ref_y = _rotate_xy(self._tcp_x, self._tcp_y, ref_rz)
        delta_x = cur_x - ref_x
        delta_y = cur_y - ref_y
        corrected = (plane_xy[0] - delta_x, plane_xy[1] - delta_y)
        return corrected, (delta_x, delta_y)


def _map_plane(xy: Tuple[float, float], mapper: Optional[PlanePoseMapper]) -> Tuple[float, float]:
    if mapper is None:
        return xy
    return mapper.map_point(xy[0], xy[1])


def _reference_rz(mapper: Optional[PlanePoseMapper]) -> float:
    if mapper is None:
        return 0.0
    return float(mapper.target_pose.rz)


def _rotate_xy(x: float, y: float, rz_deg: float) -> Tuple[float, float]:
    angle_rad = math.radians(rz_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)


def _is_camera_point(point: EndEffectorPoint) -> bool:
    return str(point.name).strip().lower() == "camera"

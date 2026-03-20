from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.robot.plane_pose_mapper import PlanePoseMapper
from src.robot_systems.glue.targeting.end_effector_point import EndEffectorPoint
from src.robot_systems.glue.targeting.pixel_target import PixelTarget
from src.robot_systems.glue.targeting.point_registry import PointRegistry
from src.robot_systems.glue.targeting.target_frame import TargetFrame  # noqa: F401 (re-exported for callers)


@dataclass(frozen=True)
class TargetTransformResult:
    """Full intermediate and final coordinates for a single transformation.

    ``z`` is the height-correction delta in mm (``0.0`` when no correction is
    configured on the frame).  Add your own base approach height on top::

        pose = result.robot_pose(base_z=300.0)   # [x, y, z, rx, ry, rz]
    """
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

    def robot_pose(self, base_z: float = 0.0) -> Tuple[float, float, float, float, float, float]:
        """Return ``[x, y, z, rx, ry, rz]`` ready to pass to the robot driver.

        ``base_z`` is the application-level approach height in mm; the stored
        height-correction delta is added on top.
        """
        x, y = self.final_xy
        return (x, y, base_z + self.z, self.rx, self.ry, self.rz)


class VisionTargetResolver:
    """Single transformation hub: image pixel → robot XY for any end-effector point.

    Pipeline for a single ``resolve()`` call:

    1. **Homography** — pixel (px, py) → calibration-plane robot XY via
       ``base_transformer``.
    2. **Plane mapping** — calibration XY → target pose frame XY via the
       active mapper (see ``frame`` / ``mapper`` args; identity if absent).
    3. **Camera-to-TCP delta correction** — orientation-dependent correction
       for camera motion around the TCP when the wrist rotates away from the
       calibration reference angle::

           delta(rz) = R(rz)·tcp_offset − R(ref_rz)·tcp_offset

       Only applied when ``current_rz`` is provided.
    4. **End-effector offset** — rotate the point's local wrist-frame offset
       by ``current_rz`` and add to the camera-center result::

           final_xy = camera_xy + R(rz)·[offset_x, offset_y]

       Skipped for the camera point (zero offset).  Raises ``RuntimeError``
       if a non-zero offset is requested without ``current_rz``.

    Named frames
    ------------
    Pass a ``frames`` dict at construction to register named coordinate planes.
    Each entry is a ``TargetFrame`` that bundles the plane mapper and (optionally)
    a height-correction service for that plane::

        resolver = VisionTargetResolver(...,
            frames={
                TargetFrame.CALIBRATION: TargetFrame(TargetFrame.CALIBRATION,
                                                     height_correction=depth_map_service),
                TargetFrame.PICKUP: TargetFrame(TargetFrame.PICKUP,
                                                     mapper=pickup_mapper),
            },)

    The resolver uses only ``TargetFrame.mapper`` for XY conversion.  The
    application layer reads ``TargetFrame.height_correction`` for Z.

    Select a frame per call::

        result = resolver.resolve_named(PixelTarget(px, py, rz=rz), "tool", frame=TargetFrame.PICKUP)

    For dynamic one-off mappers (e.g. per-capture-pose remapping), pass
    ``mapper=`` directly — it takes precedence over the frame's mapper::

        result = resolver.resolve(PixelTarget(px, py, rz=rz), point, mapper=capture_mapper)
    """

    def __init__(
        self,
        base_transformer: ICoordinateTransformer,
        registry: PointRegistry,
        camera_to_tcp_x_offset: float = 0.0,
        camera_to_tcp_y_offset: float = 0.0,
        frames: Optional[Dict[str, TargetFrame]] = None,
    ) -> None:
        self._base     = base_transformer
        self._registry = registry
        self._tcp_x    = float(camera_to_tcp_x_offset)
        self._tcp_y    = float(camera_to_tcp_y_offset)
        self._frames: Dict[str, TargetFrame] = frames or {}

    # ── Public API ────────────────────────────────────────────────────────────

    def resolve(
        self,
        target: PixelTarget,
        point: EndEffectorPoint,
        *,
        frame: str = TargetFrame.CALIBRATION,
        mapper: Optional[PlanePoseMapper] = None,
    ) -> TargetTransformResult:
        """Transform a ``PixelTarget`` so that ``point`` ends up at the robot target.

        Args:
            target: Image-space detection point with capture-time orientation.
            point: The end-effector point to use as the physical target.
            frame: Named coordinate frame registered in ``frames``.  Ignored
                when ``mapper`` is given explicitly.
            mapper: One-off plane mapper.  Takes precedence over ``frame``.

        ``TargetTransformResult.z`` is the height-correction delta in mm.
        Use ``result.robot_pose(base_z)`` to get the full ``[x, y, z, rx, ry, rz]``
        ready to pass to the robot driver.
        """
        frame_obj     = self._frames.get(frame)
        active_mapper = mapper if mapper is not None else (frame_obj.mapper if frame_obj else None)
        current_rz    = target.rz

        # Step 1: homography → calibration plane
        calibration_xy = self._base.transform(target.px, target.py)

        # Step 2: map into target pose frame (if mapper present)
        plane_xy = _map_plane(calibration_xy, active_mapper)

        # Step 3: camera-to-TCP delta correction
        camera_xy, tcp_delta = self._apply_tcp_delta(plane_xy, current_rz, active_mapper)

        # Step 4: rotate end-effector offset and add
        if point.offset_x == 0.0 and point.offset_y == 0.0:
            final_xy     = camera_xy
            target_delta = (0.0, 0.0)
        else:
            dx, dy       = _rotate_xy(point.offset_x, point.offset_y, current_rz)
            final_xy     = (camera_xy[0] + dx, camera_xy[1] + dy)
            target_delta = (dx, dy)

        # Step 5: height correction delta Z (0.0 when not configured on this frame)
        z = frame_obj.get_z_correction(final_xy[0], final_xy[1]) if frame_obj is not None else 0.0

        return TargetTransformResult(
            calibration_xy=calibration_xy,
            plane_xy=plane_xy,
            final_xy=final_xy,
            rx=target.rx,
            ry=target.ry,
            rz=current_rz if current_rz is not None else 0.0,
            z=z,
            pickup_plane_reference_delta_xy=tcp_delta,
            target_delta_xy=target_delta,
            reference_rz=_reference_rz(active_mapper),
        )

    def resolve_named(
        self,
        target: PixelTarget,
        name: str,
        *,
        frame: str = TargetFrame.CALIBRATION,
        mapper: Optional[PlanePoseMapper] = None,
    ) -> TargetTransformResult:
        """Convenience wrapper — looks up the point by name then calls ``resolve``."""
        return self.resolve(target, self._registry.by_name(name), frame=frame, mapper=mapper)

    @property
    def registry(self) -> PointRegistry:
        return self._registry

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _apply_tcp_delta(
        self,
        plane_xy: Tuple[float, float],
        current_rz: Optional[float],
        active_mapper: Optional[PlanePoseMapper],
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Apply the orientation-dependent camera-to-TCP delta correction."""
        if current_rz is None or (self._tcp_x == 0.0 and self._tcp_y == 0.0):
            return plane_xy, (0.0, 0.0)

        ref_rz   = _reference_rz(active_mapper)
        cur_x, cur_y = _rotate_xy(self._tcp_x, self._tcp_y, current_rz)
        ref_x, ref_y = _rotate_xy(self._tcp_x, self._tcp_y, ref_rz)
        delta_x  = cur_x - ref_x
        delta_y  = cur_y - ref_y
        corrected = (plane_xy[0] - delta_x, plane_xy[1] - delta_y)
        return corrected, (delta_x, delta_y)


# ── Module-level helpers ───────────────────────────────────────────────────────

def _map_plane(
    xy: Tuple[float, float],
    mapper: Optional[PlanePoseMapper],
) -> Tuple[float, float]:
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

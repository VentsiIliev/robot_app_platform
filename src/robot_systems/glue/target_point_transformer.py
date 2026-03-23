from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.robot.plane_pose_mapper import PlanePoseMapper


@dataclass(frozen=True)
class TargetTransformResult:
    calibration_xy: Tuple[float, float]
    plane_xy: Tuple[float, float]
    final_xy: Tuple[float, float]
    pickup_plane_reference_delta_xy: Tuple[float, float] = (0.0, 0.0)
    target_delta_xy: Tuple[float, float] = (0.0, 0.0)
    current_rz: Optional[float] = None
    reference_rz: Optional[float] = None

# homography → plane → camera alignment → rotate offset → add
class TargetPointTransformer:
    """Higher-level image->robot transformer with glue-specific target semantics.

    This sits one layer above ``HomographyTransformer``. The base homography
    always maps image pixels into the calibration-plane robot frame. This helper
    then adds the glue-system meaning that callers actually care about:

    - whether the point should remain in calibration-plane XY or be mapped into
      another robot pose frame through ``PlanePoseMapper``
    - which physical point should act as the target reference (`camera`, `tcp`,
      `tool`, or `gripper`)
    - whether an orientation-dependent camera-to-TCP correction must be applied

    Why the mapped-pose reference delta exists:

    The base homography is calibrated at the calibration pose. When a
    ``PlanePoseMapper`` is present, the point is first mapped into that target
    pose frame. Empirically, the mapped point is already correct at the target
    pose reference orientation. Applying the full camera-to-TCP offset again at
    that same reference orientation moves the robot away from the target.

    Because of that, mapped camera-center targeting uses only the
    orientation-dependent *change* from the mapped-frame reference:

        delta(rz_degrees) = R(rz_degrees) * camera_to_tcp - R(reference_rz) * camera_to_tcp

    and the corrected mapped target becomes:

        corrected_xy = mapped_xy - delta(rz_degrees)

    ``reference_rz`` comes from ``PlanePoseMapper.target_pose.rz_degrees`` when a mapper
    exists, or falls back to `0°` for calibration-plane use.
    """

    def __init__(
        self,
        base_transformer: ICoordinateTransformer,
        calibration_to_target_pose_mapper: Optional[PlanePoseMapper] = None,
        camera_to_tcp_x_offset: float = 0.0,
        camera_to_tcp_y_offset: float = 0.0,
        camera_center_point: Optional[Tuple[float, float]] = None,
        gripper_point: Optional[Tuple[float, float]] = None,
    ):
        """Build a target-point resolver on top of a raw calibration-plane transformer.

        Args:
            base_transformer: Usually ``HomographyTransformer``. Must provide the
                calibration-plane image->robot transform and optional TCP/tool
                helpers.
            calibration_to_target_pose_mapper: Optional rigid mapper object from
                calibration-plane XY into a target pose frame XY.
            camera_to_tcp_x_offset: Local camera->TCP X offset used for
                orientation-dependent mapped-frame camera-center compensation.
            camera_to_tcp_y_offset: Local camera->TCP Y offset used for
                orientation-dependent mapped-frame camera-center compensation.
            camera_center_point: Optional measured camera-center XY at the
                common calibration reference point.
            gripper_point: Optional measured gripper XY at the same physical
                point.
        """
        self._base_transformer = base_transformer
        self._calibration_to_target_pose_mapper = calibration_to_target_pose_mapper
        self._camera_to_tcp_x_offset = float(camera_to_tcp_x_offset)
        self._camera_to_tcp_y_offset = float(camera_to_tcp_y_offset)
        self._camera_center_point = camera_center_point
        self._gripper_point = gripper_point

    def transform_to_camera_center(
        self,
        px: float,
        py: float,
        *,
        current_rz: Optional[float] = None,
    ) -> TargetTransformResult:
        """Transform an image point so the camera center acts as the target point.

        When no mapper is configured, this is just raw calibration-plane
        homography output.

        When mapping is enabled, this returns the mapped target-plane point, and if
        ``current_rz`` is provided, it also applies the camera-to-TCP *delta*
        correction relative to the mapper target pose `rz_degrees`. This preserves the
        known-good baseline at the mapped-frame reference angle while
        compensating for camera motion around the TCP at other wrist
        orientations.
        """
        calibration_xy = self._base_transformer.transform(px, py)
        plane_xy = self._map_plane(calibration_xy)
        final_xy = plane_xy
        delta_xy = (0.0, 0.0)

        if current_rz is not None:
            final_xy, delta_xy = self._apply_pickup_plane_tcp_delta(plane_xy, current_rz)

        return TargetTransformResult(
            calibration_xy=calibration_xy,
            plane_xy=plane_xy,
            final_xy=final_xy,
            pickup_plane_reference_delta_xy=delta_xy,
            current_rz=current_rz,
            reference_rz=self._reference_rz(),
        )

    def transform_to_tcp(
        self,
        px: float,
        py: float,
    ) -> TargetTransformResult:
        """Transform an image point so the robot TCP acts as the target point.

        This uses the base transformer's explicit camera-to-TCP offset helper,
        then optionally maps the resulting point into the target pose plane.
        """
        calibration_xy = self._base_transformer.transform_to_tcp(px, py)
        plane_xy = self._map_plane(calibration_xy)
        return TargetTransformResult(
            calibration_xy=calibration_xy,
            plane_xy=plane_xy,
            final_xy=plane_xy,
        )

    def transform_to_gripper(
        self,
        px: float,
        py: float,
        *,
        current_rz: float
    ) -> TargetTransformResult:
        """Transform an image point so the gripper acts as the target point.

        This derives ``camera_to_gripper`` from the measured reference points
        ``gripper_point - camera_center_point`` and then applies that local
        offset through the shared rotated-offset path.
        """
        camera_to_gripper = self._camera_to_gripper_offset()

        if camera_to_gripper is None:
            raise RuntimeError(
                "Gripper targeting requires measured camera_center/gripper_point reference values"
            )

        return self._transform_camera_to_target(
            px,
            py,
            current_rz=current_rz,
            camera_offset=camera_to_gripper,
        )

    @staticmethod
    def compute_offset(
        from_point: Tuple[float, float],
        to_point: Tuple[float, float],
    ) -> Tuple[float, float]:
        """Return ``to_point - from_point`` for measured XY reference points."""
        return (to_point[0] - from_point[0], to_point[1] - from_point[1])

    def get_camera_to_gripper_offset(self) -> Optional[Tuple[float, float]]:
        """Return the measured camera->gripper offset when available."""
        return self._camera_to_gripper_offset()

    @classmethod
    def apply_offset(
        cls,
        offset_xy: Tuple[float, float],
        rz_deg: float,
    ) -> Tuple[float, float]:
        """Rotate a local XY offset into the world plane at ``rz_deg``."""
        return cls._rotate_xy(offset_xy[0], offset_xy[1], rz_deg)

    def _map_plane(self, xy: Tuple[float, float]) -> Tuple[float, float]:
        """Return the point in the configured target frame, if a mapper exists."""
        if self._calibration_to_target_pose_mapper is None:
            return xy
        return self._calibration_to_target_pose_mapper.map_point(xy[0], xy[1])

    def _apply_pickup_plane_tcp_delta(
        self,
        plane_xy: Tuple[float, float],
        current_rz: float,
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Apply only the mapped-frame camera-to-TCP delta from the reference angle.

        The mapped point is already correct at the mapped-frame reference
        orientation. For any other ``current_rz`` we compensate only for the
        change in camera position caused by rotating around the TCP:

            delta(rz_degrees) = R(rz_degrees) * c - R(reference_rz) * c

        The returned tuple is:
        - corrected point in mapped target-frame XY
        - the delta vector that was applied
        """
        tx = self._camera_to_tcp_x_offset
        ty = self._camera_to_tcp_y_offset
        if tx == 0.0 and ty == 0.0:
            return plane_xy, (0.0, 0.0)

        cur_x, cur_y = self._rotate_xy(tx, ty, current_rz)
        ref_x, ref_y = self._rotate_xy(tx, ty, self._reference_rz())
        delta_x = cur_x - ref_x
        delta_y = cur_y - ref_y
        corrected_xy = (plane_xy[0] - delta_x, plane_xy[1] - delta_y)
        return corrected_xy, (delta_x, delta_y)

    def _reference_rz(self) -> float:
        if self._calibration_to_target_pose_mapper is None:
            return 0.0
        return float(self._calibration_to_target_pose_mapper.target_pose.rz)

    def _transform_camera_to_target(
        self,
        px: float,
        py: float,
        *,
        current_rz: Optional[float],
        camera_offset: Tuple[float, float],
    ) -> TargetTransformResult:
        """Resolve a camera-centered target, rotate one local offset, and apply it.

        This is the shared implementation used by tool and gripper targeting:

        1. resolve the image point to a camera-centered target
        2. rotate the supplied camera->target offset by ``current_rz``
        3. add the rotated offset to produce the requested physical target point
        """
        if current_rz is None:
            raise RuntimeError("Target targeting requires current_rz")
        camera_result = self.transform_to_camera_center(
            px,
            py,
            current_rz=current_rz,
        )
        delta_x, delta_y = self.apply_offset(camera_offset, current_rz)
        final_xy = (
            camera_result.final_xy[0] + delta_x,
            camera_result.final_xy[1] + delta_y,
        )
        return TargetTransformResult(
            calibration_xy=camera_result.calibration_xy,
            plane_xy=camera_result.plane_xy,
            final_xy=final_xy,
            pickup_plane_reference_delta_xy=camera_result.pickup_plane_reference_delta_xy,
            target_delta_xy=(delta_x, delta_y),
            current_rz=current_rz,
            reference_rz=camera_result.reference_rz,
        )

    def _camera_to_gripper_offset(self) -> Optional[Tuple[float, float]]:
        """Return camera->gripper from measured reference points when available."""
        if self._camera_center_point is not None and self._gripper_point is not None:
            return self.compute_offset(self._camera_center_point, self._gripper_point)
        return None

    @staticmethod
    def _rotate_xy(x: float, y: float, rz_deg: float) -> Tuple[float, float]:
        """Rotate a local XY offset vector by ``rz_deg`` in the plane."""
        angle_rad = math.radians(rz_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Literal, Optional, Tuple

from src.engine.core.i_coordinate_transformer import ICoordinateTransformer

PlaneName = Literal["calibration", "pickup"]


@dataclass(frozen=True)
class TargetTransformResult:
    calibration_xy: Tuple[float, float]
    plane_xy: Tuple[float, float]
    final_xy: Tuple[float, float]
    pickup_plane_tcp_delta_xy: Tuple[float, float] = (0.0, 0.0)
    target_delta_xy: Tuple[float, float] = (0.0, 0.0)
    current_rz: Optional[float] = None
    reference_rz: Optional[float] = None


class TargetPointTransformer:
    """Higher-level image->robot transformer with glue-specific plane/target semantics.

    This sits one layer above ``HomographyTransformer``. The base homography
    always maps image pixels into the calibration-plane robot frame. This helper
    then adds the glue-system meaning that callers actually care about:

    - which plane the point should be expressed in (`calibration` or `pickup`)
    - which physical point should act as the target reference (`camera`, `tcp`,
      or `tool`)
    - whether an orientation-dependent camera-to-TCP correction must be applied

    Why the pickup-plane delta exists:

    In the glue system the calibration homography is built from the calibration
    pose, then the point is mapped into the pickup plane. Empirically, the
    mapped pickup-plane point is already correct at the working pickup reference
    orientation (`90°`). Applying the full camera-to-TCP offset again at that
    orientation moves the robot away from the target.

    Because of that, pickup-plane camera-center targeting uses only the
    orientation-dependent *change* from the known-good pickup reference:

        delta(rz) = R(rz) * camera_to_tcp - R(reference_rz) * camera_to_tcp

    and the corrected pickup target becomes:

        corrected_xy = mapped_pickup_xy - delta(rz)

    This guarantees that when ``current_rz == reference_rz`` (currently `90°`)
    the correction is zero, so the existing working baseline is preserved.
    """

    def __init__(
        self,
        base_transformer: ICoordinateTransformer,
        calibration_to_pickup_mapper: Optional[Callable[[float, float], tuple[float, float]]] = None,
        camera_to_tcp_x_offset: float = 0.0,
        camera_to_tcp_y_offset: float = 0.0,
        camera_to_tool_x_offset: float = 0.0,
        camera_to_tool_y_offset: float = 0.0,
        pickup_plane_reference_rz: float = 90.0,
    ):
        """Build a target-point resolver on top of a raw calibration-plane transformer.

        Args:
            base_transformer: Usually ``HomographyTransformer``. Must provide the
                calibration-plane image->robot transform and optional TCP/tool
                helpers.
            calibration_to_pickup_mapper: Optional rigid mapper from
                calibration-plane XY into pickup-plane XY.
            camera_to_tcp_x_offset: Local camera->TCP X offset used for
                orientation-dependent pickup-plane camera-center compensation.
            camera_to_tcp_y_offset: Local camera->TCP Y offset used for
                orientation-dependent pickup-plane camera-center compensation.
            camera_to_tool_x_offset: Local camera->tool X offset in the
                calibration reference frame.
            camera_to_tool_y_offset: Local camera->tool Y offset in the
                calibration reference frame.
            pickup_plane_reference_rz: The known-good pickup-plane orientation
                where the mapped point already aligns correctly. At this angle
                the TCP delta must evaluate to zero.
        """
        self._base_transformer = base_transformer
        self._calibration_to_pickup_mapper = calibration_to_pickup_mapper
        self._camera_to_tcp_x_offset = float(camera_to_tcp_x_offset)
        self._camera_to_tcp_y_offset = float(camera_to_tcp_y_offset)
        self._camera_to_tool_x_offset = float(camera_to_tool_x_offset)
        self._camera_to_tool_y_offset = float(camera_to_tool_y_offset)
        self._pickup_plane_reference_rz = float(pickup_plane_reference_rz)

    def transform_to_camera_center(
        self,
        px: float,
        py: float,
        *,
        plane: PlaneName = "calibration",
        current_rz: Optional[float] = None,
    ) -> TargetTransformResult:
        """Transform an image point so the camera center acts as the target point.

        In calibration-plane mode this is just raw homography output.

        In pickup-plane mode this returns the mapped pickup-plane point, and if
        ``current_rz`` is provided, it also applies the camera-to-TCP *delta*
        correction relative to ``pickup_plane_reference_rz``. This preserves the
        known-good baseline at the reference angle while compensating for camera
        motion around the TCP at other wrist orientations.
        """
        calibration_xy = self._base_transformer.transform(px, py)
        plane_xy = self._map_plane(calibration_xy, plane)
        final_xy = plane_xy
        delta_xy = (0.0, 0.0)

        if plane == "pickup" and current_rz is not None:
            final_xy, delta_xy = self._apply_pickup_plane_tcp_delta(plane_xy, current_rz)

        return TargetTransformResult(
            calibration_xy=calibration_xy,
            plane_xy=plane_xy,
            final_xy=final_xy,
            pickup_plane_tcp_delta_xy=delta_xy,
            current_rz=current_rz,
            reference_rz=self._pickup_plane_reference_rz if plane == "pickup" else None,
        )

    def transform_to_tcp(
        self,
        px: float,
        py: float,
        *,
        plane: PlaneName = "calibration",
    ) -> TargetTransformResult:
        """Transform an image point so the robot TCP acts as the target point.

        This uses the base transformer's explicit camera-to-TCP offset helper,
        then optionally maps the resulting point into the pickup plane.
        """
        calibration_xy = self._base_transformer.transform_to_tcp(px, py)
        plane_xy = self._map_plane(calibration_xy, plane)
        return TargetTransformResult(
            calibration_xy=calibration_xy,
            plane_xy=plane_xy,
            final_xy=plane_xy,
        )

    def transform_to_tool(
        self,
        px: float,
        py: float,
        *,
        plane: PlaneName = "calibration",
    ) -> TargetTransformResult:
        """Transform an image point so the active tool point acts as the target.

        This uses the base transformer's explicit camera-to-tool offset helper,
        then optionally maps the resulting point into the pickup plane.
        """
        calibration_xy = self._base_transformer.transform_to_tool(px, py)
        plane_xy = self._map_plane(calibration_xy, plane)
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
        plane: PlaneName = "calibration",
        current_rz: float,
        tool_to_gripper_x_offset: float = 0.0,
        tool_to_gripper_y_offset: float = 0.0,
    ) -> TargetTransformResult:
        """Transform an image point so the gripper acts as the target point.

        The computation is layered on top of camera-center targeting:

        1. Resolve the point that makes the camera center align with the target.
        2. Compute the local camera->gripper vector as:
           ``camera_to_tool + tool_to_gripper``.
        3. Rotate that vector by ``current_rz`` and add it to the resolved
           camera-centered target.

        This keeps all camera/TCP pickup-plane delta logic in one place while
        letting callers request gripper targeting with a single call.
        """
        camera_result = self.transform_to_camera_center(
            px,
            py,
            plane=plane,
            current_rz=current_rz,
        )
        cam_to_gripper_x = self._camera_to_tool_x_offset + float(tool_to_gripper_x_offset)
        cam_to_gripper_y = self._camera_to_tool_y_offset + float(tool_to_gripper_y_offset)
        delta_x, delta_y = self._rotate_xy(cam_to_gripper_x, cam_to_gripper_y, current_rz)
        final_xy = (
            camera_result.final_xy[0] + delta_x,
            camera_result.final_xy[1] + delta_y,
        )
        return TargetTransformResult(
            calibration_xy=camera_result.calibration_xy,
            plane_xy=camera_result.plane_xy,
            final_xy=final_xy,
            pickup_plane_tcp_delta_xy=camera_result.pickup_plane_tcp_delta_xy,
            target_delta_xy=(delta_x, delta_y),
            current_rz=current_rz,
            reference_rz=camera_result.reference_rz,
        )

    def _map_plane(self, xy: Tuple[float, float], plane: PlaneName) -> Tuple[float, float]:
        """Return the point in the requested plane frame.

        Calibration-plane points pass through unchanged. Pickup-plane points are
        converted via the configured calibration-to-pickup rigid mapper.
        """
        if plane == "calibration":
            return xy
        if self._calibration_to_pickup_mapper is None:
            raise RuntimeError("Pickup-plane mapper is not available")
        return self._calibration_to_pickup_mapper(xy[0], xy[1])

    def _apply_pickup_plane_tcp_delta(
        self,
        plane_xy: Tuple[float, float],
        current_rz: float,
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Apply only the pickup-plane camera-to-TCP delta from the reference angle.

        The pickup-plane mapped point is already correct at the reference pickup
        orientation. For any other ``current_rz`` we compensate only for the
        change in camera position caused by rotating around the TCP:

            delta(rz) = R(rz) * c - R(reference_rz) * c

        The returned tuple is:
        - corrected point in pickup-plane XY
        - the delta vector that was applied
        """
        tx = self._camera_to_tcp_x_offset
        ty = self._camera_to_tcp_y_offset
        if tx == 0.0 and ty == 0.0:
            return plane_xy, (0.0, 0.0)

        cur_x, cur_y = self._rotate_xy(tx, ty, current_rz)
        ref_x, ref_y = self._rotate_xy(tx, ty, self._pickup_plane_reference_rz)
        delta_x = cur_x - ref_x
        delta_y = cur_y - ref_y
        corrected_xy = (plane_xy[0] - delta_x, plane_xy[1] - delta_y)
        return corrected_xy, (delta_x, delta_y)

    @staticmethod
    def _rotate_xy(x: float, y: float, rz_deg: float) -> Tuple[float, float]:
        """Rotate a local XY offset vector by ``rz_deg`` in the plane."""
        angle_rad = math.radians(rz_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class PlanePose:
    x: float
    y: float
    rz: float


class CalibrationToPickupPlaneMapper:
    """Maps calibration-plane robot XY points into the pickup-plane frame."""

    def __init__(self, calibration_pose: PlanePose, pickup_pose: PlanePose):
        self._calibration_pose = calibration_pose
        self._pickup_pose = pickup_pose
        self._logger = logging.getLogger(__name__)

        self._delta_rz_deg = pickup_pose.rz - calibration_pose.rz
        self._delta_rz_rad = math.radians(self._delta_rz_deg)
        self._cos_delta = math.cos(self._delta_rz_rad)
        self._sin_delta = math.sin(self._delta_rz_rad)

        self._logger.info(
            "CalibrationToPickupPlaneMapper initialized: calibration=(%.3f, %.3f, rz=%.3f), "
            "pickup=(%.3f, %.3f, rz=%.3f), delta_rz=%.3f",
            calibration_pose.x,
            calibration_pose.y,
            calibration_pose.rz,
            pickup_pose.x,
            pickup_pose.y,
            pickup_pose.rz,
            self._delta_rz_deg,
        )

    @classmethod
    def from_positions(
        cls,
        calibration_position: Sequence[float],
        pickup_position: Sequence[float],
    ) -> "CalibrationToPickupPlaneMapper":
        return cls(
            calibration_pose=PlanePose(
                x=float(calibration_position[0]),
                y=float(calibration_position[1]),
                rz=float(calibration_position[5]),
            ),
            pickup_pose=PlanePose(
                x=float(pickup_position[0]),
                y=float(pickup_position[1]),
                rz=float(pickup_position[5]),
            ),
        )

    def map_point(self, x: float, y: float) -> tuple[float, float]:
        rel_x = float(x) - self._calibration_pose.x
        rel_y = float(y) - self._calibration_pose.y

        rotated_x = rel_x * self._cos_delta - rel_y * self._sin_delta
        rotated_y = rel_x * self._sin_delta + rel_y * self._cos_delta

        mapped_x = self._pickup_pose.x + rotated_x
        mapped_y = self._pickup_pose.y + rotated_y

        self._logger.debug(
            "Mapped calibration-plane point (%.3f, %.3f) -> relative (%.3f, %.3f) -> "
            "rotated (%.3f, %.3f) -> pickup-plane (%.3f, %.3f)",
            x,
            y,
            rel_x,
            rel_y,
            rotated_x,
            rotated_y,
            mapped_x,
            mapped_y,
        )
        return mapped_x, mapped_y

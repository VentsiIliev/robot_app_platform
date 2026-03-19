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


class PlanePoseMapper:
    """Map robot XY points from one pose frame into another pose frame."""

    def __init__(self, source_pose: PlanePose, target_pose: PlanePose):
        self._source_pose = source_pose
        self._target_pose = target_pose
        self._logger = logging.getLogger(__name__)

        self._delta_rz_deg = target_pose.rz - source_pose.rz
        self._delta_rz_rad = math.radians(self._delta_rz_deg)
        self._cos_delta = math.cos(self._delta_rz_rad)
        self._sin_delta = math.sin(self._delta_rz_rad)

        self._logger.info(
            "PlanePoseMapper initialized: source=(%.3f, %.3f, rz=%.3f), "
            "target=(%.3f, %.3f, rz=%.3f), delta_rz=%.3f",
            source_pose.x,
            source_pose.y,
            source_pose.rz,
            target_pose.x,
            target_pose.y,
            target_pose.rz,
            self._delta_rz_deg,
        )

    @property
    def source_pose(self) -> PlanePose:
        return self._source_pose

    @property
    def target_pose(self) -> PlanePose:
        return self._target_pose

    @classmethod
    def from_positions(
        cls,
        source_position: Sequence[float],
        target_position: Sequence[float],
    ) -> "PlanePoseMapper":
        return cls(
            source_pose=PlanePose(
                x=float(source_position[0]),
                y=float(source_position[1]),
                rz=float(source_position[5]),
            ),
            target_pose=PlanePose(
                x=float(target_position[0]),
                y=float(target_position[1]),
                rz=float(target_position[5]),
            ),
        )

    def map_point(self, x: float, y: float) -> tuple[float, float]:
        rel_x = float(x) - self._source_pose.x
        rel_y = float(y) - self._source_pose.y

        rotated_x = rel_x * self._cos_delta - rel_y * self._sin_delta
        rotated_y = rel_x * self._sin_delta + rel_y * self._cos_delta

        mapped_x = self._target_pose.x + rotated_x
        mapped_y = self._target_pose.y + rotated_y

        self._logger.debug(
            "Mapped source-plane point (%.3f, %.3f) -> relative (%.3f, %.3f) -> "
            "rotated (%.3f, %.3f) -> target-plane (%.3f, %.3f)",
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

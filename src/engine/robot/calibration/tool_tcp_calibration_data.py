from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence, cast


Pose6 = tuple[float, float, float, float, float, float]
Point3 = tuple[float, float, float]


@dataclass(frozen=True)
class ToolTcpSample:
    """One flange pose captured while the physical TCP touches the pivot point."""

    flange_pose: Pose6

    @classmethod
    def from_pose(cls, pose: Sequence[float]) -> "ToolTcpSample":
        return cls(flange_pose=_pose6(pose))

    def to_dict(self) -> dict:
        return {"flange_pose": list(self.flange_pose)}


@dataclass(frozen=True)
class ToolTcpCalibrationResult:
    """Solved flange-to-TCP offset and fit quality from pivot calibration samples."""

    tool_offset: Pose6
    pivot_point: Point3
    residual_rms_mm: float
    residual_max_mm: float
    sample_count: int

    @classmethod
    def from_values(
        cls,
        tool_offset: Sequence[float],
        pivot_point: Sequence[float],
        residual_rms_mm: float,
        residual_max_mm: float,
        sample_count: int,
    ) -> "ToolTcpCalibrationResult":
        return cls(
            tool_offset=_pose6(tool_offset),
            pivot_point=_point3(pivot_point),
            residual_rms_mm=float(residual_rms_mm),
            residual_max_mm=float(residual_max_mm),
            sample_count=int(sample_count),
        )

    def to_dict(self) -> dict:
        return {
            "tool_offset": list(self.tool_offset),
            "pivot_point": list(self.pivot_point),
            "residual_rms_mm": self.residual_rms_mm,
            "residual_max_mm": self.residual_max_mm,
            "sample_count": self.sample_count,
        }


def _pose6(values: Sequence[float]) -> Pose6:
    if len(values) != 6:
        raise ValueError("pose must contain exactly 6 values [x, y, z, rx, ry, rz]")
    parsed = tuple(_finite_float(value) for value in values)
    return cast(Pose6, parsed)


def _point3(values: Sequence[float]) -> Point3:
    if len(values) != 3:
        raise ValueError("point must contain exactly 3 values [x, y, z]")
    parsed = tuple(_finite_float(value) for value in values)
    return cast(Point3, parsed)


def _finite_float(value: float) -> float:
    parsed = float(value)
    if not isfinite(parsed):
        raise ValueError("calibration values must be finite")
    return parsed

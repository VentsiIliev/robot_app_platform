from __future__ import annotations

import math
from collections.abc import Sequence

from src.engine.robot.tool_transform import inverse_rotate, rotation_matrix, rotate


class RelativeToolCalibrationService:
    """Calibrate a tool TCP by touching a point previously captured with a reference tool."""

    def __init__(self, *, minimum_samples: int = 3):
        self._minimum_samples = max(1, int(minimum_samples))
        self._reference_point: list[float] | None = None
        self._reference_transform: list[float] | None = None
        self._candidate_translations: list[list[float]] = []

    def capture_reference(self, flange_pose: Sequence[float], tool_transform: Sequence[float]) -> None:
        self._validate_pose(flange_pose, "flange_pose")
        self._validate_pose(tool_transform, "tool_transform")
        flange_rotation = rotation_matrix(*flange_pose[3:6])
        tcp_in_base = rotate(flange_rotation, tool_transform[:3])
        self._reference_point = [float(flange_pose[i]) + tcp_in_base[i] for i in range(3)]
        self._reference_transform = [float(value) for value in tool_transform]
        self._candidate_translations.clear()

    def capture_candidate(self, flange_pose: Sequence[float]) -> list[float]:
        self._validate_pose(flange_pose, "flange_pose")
        if self._reference_point is None:
            raise RuntimeError("Capture the reference contact point first")
        delta_base = [self._reference_point[i] - float(flange_pose[i]) for i in range(3)]
        candidate = inverse_rotate(rotation_matrix(*flange_pose[3:6]), delta_base)
        self._candidate_translations.append(candidate)
        return list(candidate)

    def solve(self) -> dict:
        if self._reference_transform is None:
            raise RuntimeError("Capture the reference contact point first")
        if len(self._candidate_translations) < self._minimum_samples:
            raise RuntimeError(
                f"Capture at least {self._minimum_samples} candidate samples"
            )
        mean = [
            sum(sample[axis] for sample in self._candidate_translations) / len(self._candidate_translations)
            for axis in range(3)
        ]
        deviations = [
            math.sqrt(sum((sample[axis] - mean[axis]) ** 2 for axis in range(3)))
            for sample in self._candidate_translations
        ]
        ref = self._reference_transform
        absolute = mean + [float(value) for value in ref[3:6]]
        relative_base = [mean[i] - float(ref[i]) for i in range(3)]
        relative_local = inverse_rotate(rotation_matrix(*ref[3:6]), relative_base)
        return {
            "absolute_transform": absolute,
            "relative_transform": relative_local + [0.0, 0.0, 0.0],
            "sample_count": len(self._candidate_translations),
            "max_spread_mm": max(deviations, default=0.0),
        }

    def clear(self) -> None:
        self._reference_point = None
        self._reference_transform = None
        self._candidate_translations.clear()

    @staticmethod
    def _validate_pose(values: Sequence[float], label: str) -> None:
        if len(values) != 6:
            raise ValueError(f"{label} must contain six values")
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError(f"{label} must contain finite values")

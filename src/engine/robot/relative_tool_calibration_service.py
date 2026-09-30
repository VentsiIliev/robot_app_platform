from __future__ import annotations

import logging
import math
from collections.abc import Sequence

from src.engine.robot.tool_transform import inverse_rotate, rotation_matrix, rotate


_logger = logging.getLogger(__name__)


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
        _logger.info(
            "[TOOL_CALIBRATION] reference_captured flange_pose=%s reference_tool_transform=%s "
            "tcp_vector_in_base=%s fixed_contact_point=%s",
            _rounded(flange_pose),
            _rounded(tool_transform),
            _rounded(tcp_in_base),
            _rounded(self._reference_point),
        )

    def capture_candidate(self, flange_pose: Sequence[float]) -> list[float]:
        self._validate_pose(flange_pose, "flange_pose")
        if self._reference_point is None:
            raise RuntimeError("Capture the reference contact point first")
        delta_base = [self._reference_point[i] - float(flange_pose[i]) for i in range(3)]
        candidate = inverse_rotate(rotation_matrix(*flange_pose[3:6]), delta_base)
        self._candidate_translations.append(candidate)
        _logger.info(
            "[TOOL_CALIBRATION] candidate_captured sample=%d flange_pose=%s "
            "contact_minus_flange_base=%s candidate_tcp_local=%s",
            len(self._candidate_translations),
            _rounded(flange_pose),
            _rounded(delta_base),
            _rounded(candidate),
        )
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
        residual_vectors = [
            [sample[axis] - mean[axis] for axis in range(3)]
            for sample in self._candidate_translations
        ]
        _logger.info(
            "[TOOL_CALIBRATION] solved samples=%d candidate_tcp_local=%s mean_absolute_tcp=%s "
            "residual_vectors=%s residual_norms_mm=%s max_spread_mm=%.6f "
            "reference_tool_transform=%s relative_base=%s relative_local=%s",
            len(self._candidate_translations),
            [_rounded(sample) for sample in self._candidate_translations],
            _rounded(mean),
            [_rounded(residual) for residual in residual_vectors],
            [round(value, 6) for value in deviations],
            max(deviations, default=0.0),
            _rounded(ref),
            _rounded(relative_base),
            _rounded(relative_local),
        )
        return {
            "absolute_transform": absolute,
            "relative_transform": relative_local + [0.0, 0.0, 0.0],
            "sample_count": len(self._candidate_translations),
            "max_spread_mm": max(deviations, default=0.0),
        }

    def clear(self) -> None:
        _logger.info(
            "[TOOL_CALIBRATION] cleared reference_captured=%s candidate_samples=%d",
            self._reference_point is not None,
            len(self._candidate_translations),
        )
        self._reference_point = None
        self._reference_transform = None
        self._candidate_translations.clear()

    @staticmethod
    def _validate_pose(values: Sequence[float], label: str) -> None:
        if len(values) != 6:
            raise ValueError(f"{label} must contain six values")
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError(f"{label} must contain finite values")


def _rounded(values: Sequence[float]) -> list[float]:
    return [round(float(value), 6) for value in values]

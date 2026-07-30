from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np

from src.engine.robot.calibration.tool_tcp_calibration_data import (
    ToolTcpCalibrationResult,
    ToolTcpSample,
)


_DEFAULT_MIN_SAMPLES = 6
_RANK_TOLERANCE = 1e-9


def solve_tool_tcp_pivot(
    samples: Iterable[ToolTcpSample | Sequence[float]],
    *,
    min_samples: int = _DEFAULT_MIN_SAMPLES,
) -> ToolTcpCalibrationResult:
    normalized = [_sample_pose(sample) for sample in samples]
    if len(normalized) < int(min_samples):
        raise ValueError(f"at least {int(min_samples)} samples are required")

    rotations: list[np.ndarray] = []
    translations: list[np.ndarray] = []
    for pose in normalized:
        rotations.append(_rotation_matrix_xyz_degrees(pose[3], pose[4], pose[5]))
        translations.append(np.asarray(pose[:3], dtype=np.float64))

    a_rows = []
    b_rows = []
    identity = np.eye(3, dtype=np.float64)
    for rotation, translation in zip(rotations, translations):
        a_rows.append(np.hstack((rotation, -identity)))
        b_rows.append(-translation.reshape(3, 1))

    a_matrix = np.vstack(a_rows)
    b_vector = np.vstack(b_rows).reshape(-1)

    if not np.all(np.isfinite(a_matrix)) or not np.all(np.isfinite(b_vector)):
        raise ValueError("calibration samples must contain only finite values")

    rank = int(np.linalg.matrix_rank(a_matrix, tol=_RANK_TOLERANCE))
    if rank < 6:
        raise ValueError(
            "calibration samples are degenerate; capture more poses with different wrist orientations"
        )

    solution, _, _, _ = np.linalg.lstsq(a_matrix, b_vector, rcond=None)
    tool_offset_xyz = solution[:3]
    pivot_point = solution[3:6]

    residuals = []
    for rotation, translation in zip(rotations, translations):
        predicted = rotation @ tool_offset_xyz + translation
        residuals.append(float(np.linalg.norm(predicted - pivot_point)))

    residual_arr = np.asarray(residuals, dtype=np.float64)
    residual_rms = float(math.sqrt(float(np.mean(residual_arr * residual_arr))))
    residual_max = float(np.max(residual_arr))

    return ToolTcpCalibrationResult.from_values(
        tool_offset=[
            float(tool_offset_xyz[0]),
            float(tool_offset_xyz[1]),
            float(tool_offset_xyz[2]),
            0.0,
            0.0,
            0.0,
        ],
        pivot_point=[
            float(pivot_point[0]),
            float(pivot_point[1]),
            float(pivot_point[2]),
        ],
        residual_rms_mm=residual_rms,
        residual_max_mm=residual_max,
        sample_count=len(normalized),
    )


def _sample_pose(sample: ToolTcpSample | Sequence[float]) -> tuple[float, float, float, float, float, float]:
    if isinstance(sample, ToolTcpSample):
        return sample.flange_pose
    return ToolTcpSample.from_pose(sample).flange_pose


def _rotation_matrix_xyz_degrees(rx: float, ry: float, rz: float) -> np.ndarray:
    cx, sx = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    cy, sy = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))

    rx_m = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, cx, -sx],
            [0.0, sx, cx],
        ],
        dtype=np.float64,
    )
    ry_m = np.asarray(
        [
            [cy, 0.0, sy],
            [0.0, 1.0, 0.0],
            [-sy, 0.0, cy],
        ],
        dtype=np.float64,
    )
    rz_m = np.asarray(
        [
            [cz, -sz, 0.0],
            [sz, cz, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    return rz_m @ ry_m @ rx_m

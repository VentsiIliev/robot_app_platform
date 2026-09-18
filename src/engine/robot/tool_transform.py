from __future__ import annotations

import math
from collections.abc import Sequence


def rotation_matrix(rx_deg: float, ry_deg: float, rz_deg: float) -> list[list[float]]:
    """Return the XYZ Euler rotation used by robot tool transforms."""
    rx, ry, rz = map(math.radians, (rx_deg, ry_deg, rz_deg))
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    return [
        [cy * cz, cz * sx * sy - cx * sz, cx * cz * sy + sx * sz],
        [cy * sz, cx * cz + sx * sy * sz, cx * sy * sz - cz * sx],
        [-sy, cy * sx, cx * cy],
    ]


def rotate(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> list[float]:
    return [sum(float(matrix[row][col]) * float(vector[col]) for col in range(3)) for row in range(3)]


def inverse_rotate(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> list[float]:
    return [sum(float(matrix[col][row]) * float(vector[col]) for col in range(3)) for row in range(3)]


def compose_translation(reference: Sequence[float], relative: Sequence[float]) -> list[float]:
    """Compose a translation-only relative tool transform with an absolute reference TCP."""
    if len(reference) != 6 or len(relative) != 6:
        raise ValueError("Tool transforms must contain six values")
    rotated = rotate(rotation_matrix(*reference[3:6]), relative[:3])
    return [
        float(reference[0]) + rotated[0],
        float(reference[1]) + rotated[1],
        float(reference[2]) + rotated[2],
        float(reference[3]) + float(relative[3]),
        float(reference[4]) + float(relative[4]),
        float(reference[5]) + float(relative[5]),
    ]

"""Pure path transformations shared by paint motion workflows."""

from __future__ import annotations


def shift_path_rotation(
    path: list[list[float]],
    rotation_index: int,
    shift_degrees: float,
) -> list[list[float]]:
    """Return a copied path with a constant shift applied to one rotation component."""
    if not path:
        return []

    shift = float(shift_degrees)
    shifted = [list(pose) for pose in path]

    if abs(shift) <= 1e-9:
        return shifted

    for pose in shifted:
        if len(pose) > rotation_index:
            pose[rotation_index] = float(pose[rotation_index]) + shift

    return shifted

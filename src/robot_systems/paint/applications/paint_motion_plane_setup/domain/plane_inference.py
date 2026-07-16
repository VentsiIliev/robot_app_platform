from __future__ import annotations

import math
from dataclasses import dataclass


AXES = ("x", "y", "z")
ROT_AXES = ("rx", "ry", "rz")
POSITION_INDICES = {"x": 0, "y": 1, "z": 2}
ROTATION_INDICES = {"rx": 3, "ry": 4, "rz": 5}
ROTATION_PLANES = {
    "rx": (("y", "z"), "x"),
    "ry": (("x", "z"), "y"),
    "rz": (("x", "y"), "z"),
}


@dataclass(frozen=True)
class Pose6D:
    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float

    @classmethod
    def from_sequence(cls, values) -> "Pose6D":
        pose = list(values or [])
        if len(pose) < 6:
            raise ValueError("Expected a 6D pose [x, y, z, rx, ry, rz]")
        return cls(*(float(value) for value in pose[:6]))

    def as_list(self) -> list[float]:
        return [self.x, self.y, self.z, self.rx, self.ry, self.rz]

    def position_delta(self, other: "Pose6D") -> dict[str, float]:
        return {
            "x": other.x - self.x,
            "y": other.y - self.y,
            "z": other.z - self.z,
        }

    def rotation_delta(self, other: "Pose6D") -> dict[str, float]:
        return {
            "rx": unwrap_degrees(self.rx, other.rx) - self.rx,
            "ry": unwrap_degrees(self.ry, other.ry) - self.ry,
            "rz": unwrap_degrees(self.rz, other.rz) - self.rz,
        }


@dataclass(frozen=True)
class PlaneInference:
    translation_axis: str
    translation_direction: str
    rotation_axis: str
    planar_axes: tuple[str, str]
    fixed_axis: str
    suggested_plane_key: str
    axis_offsets_deg: dict[str, float]
    warnings: tuple[str, ...]

    def as_plane_object(self) -> dict:
        return {
            "label": self.suggested_plane_key,
            "planar_axes": list(self.planar_axes),
            "fixed_axis": self.fixed_axis,
            "rotation_axis": self.rotation_axis,
            "translation_axis": self.translation_axis,
            "translation_direction": self.translation_direction,
            "axis_offsets_deg": self.axis_offsets_deg,
        }

    def as_runtime_config(self) -> dict:
        return {
            "pivot_motion_plane": self.suggested_plane_key,
            "pivot_motion_plane_config": self.as_plane_object(),
            "pivot_translation_axis": self.translation_axis,
            "pivot_translation_direction": self.translation_direction,
            "axis_offsets_deg": self.axis_offsets_deg,
            "orientation_overrides_deg": {},
        }

    def as_paint_plane_config(
        self,
        *,
        movement_group_id: str,
        reference_pose: Pose6D | None,
    ) -> dict:
        return {
            "label": self.suggested_plane_key,
            "movement_group_id": str(movement_group_id or "").strip(),
            "reference_pose": reference_pose.as_list() if reference_pose is not None else None,
            "translation_axis": self.translation_axis,
            "translation_direction": self.translation_direction,
            "rotation_axis": self.rotation_axis,
            "fixed_axis": self.fixed_axis,
            "planar_axes": list(self.planar_axes),
            "source_planar_coordinate_indices": [0, 1],
            "planar_coordinate_indices": [
                POSITION_INDICES[axis]
                for axis in self.planar_axes
            ],
            "orthogonal_position_index": POSITION_INDICES[self.fixed_axis],
            "rotation_index": ROTATION_INDICES[self.rotation_axis],
            "axis_offsets_deg": self.axis_offsets_deg,
            "orientation_overrides_deg": {},
        }


def unwrap_degrees(reference: float, value: float) -> float:
    return math.degrees(
        math.radians(reference)
        + math.atan2(
            math.sin(math.radians(value - reference)),
            math.cos(math.radians(value - reference)),
        )
    )


def dominant_axis(deltas: dict[str, float], *, min_abs: float) -> tuple[str, float] | None:
    axis, value = max(deltas.items(), key=lambda item: abs(item[1]))
    if abs(value) < min_abs:
        return None
    return axis, value


def infer_plane(
    reference_pose: Pose6D,
    translation_pose: Pose6D,
    rotation_pose: Pose6D,
    *,
    fixed_axis_override: str | None = None,
    min_translation_mm: float = 1.0,
    min_rotation_deg: float = 1.0,
) -> PlaneInference:
    translation = dominant_axis(
        reference_pose.position_delta(translation_pose),
        min_abs=min_translation_mm,
    )
    if translation is None:
        raise ValueError(f"Translation move is too small; move at least {min_translation_mm:.1f} mm")

    rotation = dominant_axis(
        reference_pose.rotation_delta(rotation_pose),
        min_abs=min_rotation_deg,
    )
    if rotation is None:
        raise ValueError(f"Rotation move is too small; rotate at least {min_rotation_deg:.1f} deg")

    translation_axis, translation_delta = translation
    rotation_axis, _rotation_delta = rotation
    translation_direction = "forward" if translation_delta >= 0.0 else "reverse"
    warnings: list[str] = []

    if fixed_axis_override:
        fixed_axis = str(fixed_axis_override).strip().lower()
        if fixed_axis not in AXES:
            raise ValueError(f"Unsupported fixed axis: {fixed_axis_override}")
        planar_axes = tuple(axis for axis in AXES if axis != fixed_axis)
        expected_rotation_axis = f"r{fixed_axis}"
        if rotation_axis != expected_rotation_axis:
            warnings.append(
                f"Measured rotation axis '{rotation_axis.upper()}' does not match selected fixed axis "
                f"'{fixed_axis.upper()}'. A {fixed_axis.upper()}-fixed plane normally rotates around "
                f"{expected_rotation_axis.upper()}."
            )
    else:
        planar_axes, fixed_axis = ROTATION_PLANES[rotation_axis]

    if translation_axis not in planar_axes:
        warnings.append(
            f"Translation axis '{translation_axis}' is outside the inferred plane "
            f"{planar_axes[0].upper()}/{planar_axes[1].upper()}."
        )

    axis_offsets = {planar_axes[0]: 0.0, planar_axes[1]: 90.0}
    suggested_key = f"{planar_axes[0]}{planar_axes[1]}_{fixed_axis}_{rotation_axis}"
    return PlaneInference(
        translation_axis=translation_axis,
        translation_direction=translation_direction,
        rotation_axis=rotation_axis,
        planar_axes=planar_axes,
        fixed_axis=fixed_axis,
        suggested_plane_key=suggested_key,
        axis_offsets_deg=axis_offsets,
        warnings=tuple(warnings),
    )

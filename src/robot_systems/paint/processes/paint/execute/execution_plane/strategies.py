from __future__ import annotations

from dataclasses import dataclass

from src.engine.geometry.planar import unwrap_degrees


@dataclass(frozen=True)
class ExecutionPlaneStrategy:
    """Behavioral strategy for one pivot execution plane."""
    motion_plane: str
    pivot_offset_position_index: int
    rotation_axis_label: str
    requires_reachability_preflight: bool = False

    def compute_pickup_align_rotation(
        self,
        *,
        pickup_rz: float,
        pickup_ry: float,
        first_pivot_pose: list[float],
        paint_pivot_pose: list[float],
    ) -> float:
        raise NotImplementedError

    def maybe_flip_execution_rotation_direction(
        self,
        *,
        pivot_path: list[list[float]],
        enabled: bool,
    ) -> list[list[float]]:
        return pivot_path


@dataclass(frozen=True)
class XyZRzExecutionPlaneStrategy(ExecutionPlaneStrategy):
    def __init__(self) -> None:
        super().__init__(
            motion_plane="xy_z_rz",
            pivot_offset_position_index=1,
            rotation_axis_label="RZ",
            requires_reachability_preflight=False,
        )

    def compute_pickup_align_rotation(
        self,
        *,
        pickup_rz: float,
        pickup_ry: float,
        first_pivot_pose: list[float],
        paint_pivot_pose: list[float],
    ) -> float:
        return float(first_pivot_pose[5]) if len(first_pivot_pose) >= 6 else float(pickup_rz)


@dataclass(frozen=True)
class XzYRyExecutionPlaneStrategy(ExecutionPlaneStrategy):
    def __init__(self) -> None:
        super().__init__(
            motion_plane="xz_y_ry",
            pivot_offset_position_index=2,
            rotation_axis_label="RY",
            requires_reachability_preflight=True,
        )

    def compute_pickup_align_rotation(
        self,
        *,
        pickup_rz: float,
        pickup_ry: float,
        first_pivot_pose: list[float],
        paint_pivot_pose: list[float],
    ) -> float:
        target_ry = float(first_pivot_pose[4]) if len(first_pivot_pose) >= 5 else float(pickup_ry)
        reference_ry = float(paint_pivot_pose[4]) if len(paint_pivot_pose) >= 5 else float(pickup_ry)
        align_delta = unwrap_degrees(reference_ry, target_ry) - reference_ry
        return unwrap_degrees(float(pickup_rz), float(pickup_rz) + align_delta)

    def maybe_flip_execution_rotation_direction(
        self,
        *,
        pivot_path: list[list[float]],
        enabled: bool,
    ) -> list[list[float]]:
        if not enabled or not pivot_path:
            return pivot_path
        reference_ry = float(pivot_path[0][4]) if len(pivot_path[0]) >= 5 else 0.0
        for pose in pivot_path:
            if len(pose) >= 5:
                pose[4] = 2.0 * reference_ry - float(pose[4])
        return pivot_path


_STRATEGIES: dict[str, ExecutionPlaneStrategy] = {
    "xy_z_rz": XyZRzExecutionPlaneStrategy(),
    "xz_y_ry": XzYRyExecutionPlaneStrategy(),
}


def get_execution_plane_strategy(motion_plane: str) -> ExecutionPlaneStrategy:
    """Return the strategy object for a configured execution plane."""
    key = str(motion_plane or "xy_z_rz").strip().lower()
    return _STRATEGIES.get(key, _STRATEGIES["xy_z_rz"])

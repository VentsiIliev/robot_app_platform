from __future__ import annotations

from typing import Callable

import numpy as np

from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import PaintSimulationConfig
from src.robot_systems.paint.processes.paint.plan.paint_contact_motion import (
    project_paint_contact_motion_continuous,
)


def pivot_source_path(job: dict, pivot_config: PaintSimulationConfig) -> list[list[float]]:
    """Return the path used as geometric source for pivot projection."""
    path = job.get("pivot_source_path") or job.get("execution_path") or job.get("path") or []
    if isinstance(path, list):
        return path
    return [list(point) for point in path]


def projection_tool_anchor_xy(job: dict, pivot_config: PaintSimulationConfig) -> tuple[float, float] | None:
    """Return the selected tool/workpiece anchor used by pivot projection."""
    if tuple(pivot_config.source_planar_coordinate_indices) != (0, 1):
        return None
    pickup_xy = job.get("pickup_xy")
    if not pickup_xy or len(pickup_xy) < 2:
        return None
    try:
        return float(pickup_xy[0]), float(pickup_xy[1])
    except (TypeError, ValueError):
        return None


def project_pivot_paths_for_editor(
    *,
    execution_plan: WorkpieceExecutionPlan,
    pivot_config: PaintSimulationConfig,
    base_pivot_pose: list[float],
    pickup_plan,
    apply_pivot_offset: Callable[[list[float] | None, float], list[float] | None],
    resolve_pivot_offset_mm: Callable[[dict | None, WorkpieceExecutionPlan | None], float],
    align_projected_path_to_pickup_plan: Callable[[list[list[float]], object | None], list[list[float]]],
    pivot_execution_command_path: Callable[..., list[list[float]]],
    project_motion_geometry: Callable[..., tuple[list[list[float]], list[np.ndarray], list[dict[str, float | int]]]] = project_paint_contact_motion_continuous,
) -> tuple[list[list[list[float]]], list[float] | None]:
    """Project editor-visible pivot center paths for each prepared execution job."""
    paths = []
    last_pivot_pose = list(base_pivot_pose)
    for job in execution_plan.execution_jobs:
        source_path = pivot_source_path(job, pivot_config)
        if not source_path:
            continue
        pivot_pose = apply_pivot_offset(
            base_pivot_pose,
            resolve_pivot_offset_mm(job, execution_plan),
        )
        if pivot_pose is None or len(pivot_pose) < 3:
            continue
        last_pivot_pose = list(pivot_pose)
        anchor_xy = projection_tool_anchor_xy(job, pivot_config)
        center_path, _, _ = project_motion_geometry(
            source_path,
            pivot_pose,
            pivot_config,
            anchor_xy=anchor_xy,
            source_rotation_deg=(
                float(pickup_plan.source_rotation_deg)
                if pickup_plan is not None else 0.0
            ),
        )
        center_path = align_projected_path_to_pickup_plan(center_path, pickup_plan)
        center_path = pivot_execution_command_path(center_path, pickup_plan=pickup_plan)
        paths.append(center_path)
    return paths, last_pivot_pose


def project_pivot_motion_snapshots_for_editor(
    *,
    execution_plan: WorkpieceExecutionPlan,
    pivot_config: PaintSimulationConfig,
    base_pivot_pose: list[float],
    pickup_plan,
    apply_pivot_offset: Callable[[list[float] | None, float], list[float] | None],
    resolve_pivot_offset_mm: Callable[[dict | None, WorkpieceExecutionPlan | None], float],
    project_motion_geometry: Callable[..., tuple[list[list[float]], list[np.ndarray], list[dict[str, float | int]]]] = project_paint_contact_motion_continuous,
) -> tuple[list[list[np.ndarray]], list[float] | None]:
    """Return per-step projected shape snapshots for pivot motion plotting."""
    motion = []
    last_pivot_pose = list(base_pivot_pose)
    for job in execution_plan.execution_jobs:
        source_path = pivot_source_path(job, pivot_config)
        if not source_path:
            continue
        pivot_pose = apply_pivot_offset(
            base_pivot_pose,
            resolve_pivot_offset_mm(job, execution_plan),
        )
        if pivot_pose is None or len(pivot_pose) < 3:
            continue
        last_pivot_pose = list(pivot_pose)
        anchor_xy = projection_tool_anchor_xy(job, pivot_config)
        _, snapshots, _ = project_motion_geometry(
            source_path,
            pivot_pose,
            pivot_config,
            anchor_xy=anchor_xy,
            source_rotation_deg=(
                float(pickup_plan.source_rotation_deg)
                if pickup_plan is not None else 0.0
            ),
        )
        motion.append(snapshots)
    return motion, last_pivot_pose

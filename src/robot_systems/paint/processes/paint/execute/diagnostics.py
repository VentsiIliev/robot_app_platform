from __future__ import annotations

import logging
from time import perf_counter

import numpy as np

from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import (
    PAINT_PROCESS_CONFIG,
    PaintProcessConfig,
    PaintSimulationConfig,
)
from src.robot_systems.paint.processes.paint.execute.paint_debug_artifacts import (
    start_robot_motion_trace,
    write_execution_motion_trace,
    write_pivot_debug_dump,
    write_pivot_debug_plot,
)
from src.robot_systems.paint.timing import TimingRecorder

_logger = logging.getLogger(__name__)


def elapsed_s(start: float) -> float:
    return perf_counter() - float(start)


def path_length_mm(path: list[list[float]]) -> float:
    xyz = np.asarray([pose[:3] for pose in path], dtype=float)
    if len(xyz) < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(xyz, axis=0), axis=1).sum())


def diagnostics_with_command_rotation(
    diagnostics: list[dict[str, float | int]] | None,
    command_path: list[list[float]],
    rotation_index: int,
) -> list[dict[str, float | int]] | None:
    """Attach final robot-command rotation values to projection diagnostics."""
    if not diagnostics:
        return diagnostics
    adjusted: list[dict[str, float | int]] = []
    previous_rotation: float | None = None
    for index, item in enumerate(diagnostics):
        updated = dict(item)
        if index < len(command_path) and len(command_path[index]) > rotation_index:
            current_rotation = float(command_path[index][rotation_index])
            updated["command_rz"] = current_rotation
            updated["command_rotation_delta"] = (
                0.0 if previous_rotation is None else current_rotation - previous_rotation
            )
            previous_rotation = current_rotation
        adjusted.append(updated)
    return adjusted


def write_path_shape_comparison_debug(
    *,
    debug_dump_dir: str | None,
    plan: WorkpieceExecutionPlan,
) -> None:
    if not debug_dump_dir:
        return
    try:
        from src.engine.robot.path_interpolation.new_interpolation.debug_plotting import (
            write_path_shape_comparison_debug as _write_path_shape_comparison_debug,
        )

        result = _write_path_shape_comparison_debug(
            raw_paths=plan.raw_paths,
            sampled_paths=plan.sampled_paths,
            execution_paths=plan.execution_paths(),
            save_dir=debug_dump_dir,
        )
        if result:
            _logger.info("[EXECUTE] Saved path shape comparison debug artifacts: %s", result)
    except Exception:
        _logger.debug("[EXECUTE] Failed to write path shape comparison debug artifacts", exc_info=True)


def execute_paint_trajectory_with_optional_trace(
    *,
    robot_service,
    debug_dump_dir: str | None,
    pivot_config: PaintSimulationConfig,
    command_pivot_path: list[list[float]],
    vel: float,
    acc: float,
    pivot_pose: list[float] | None,
    pattern_type: str,
    stage: str,
    tcp_to_tool_local_xy: tuple[float, float] | None = None,
    paint_process_config: PaintProcessConfig | None = None,
):
    """Execute a paint trajectory and optionally write commanded-vs-actual samples."""
    config = paint_process_config or PAINT_PROCESS_CONFIG
    trace = None
    if (
        bool(getattr(config, "enable_execution_motion_trace", False))
        and robot_service is not None
    ):
        trace = start_robot_motion_trace(
            get_pose=robot_service.get_current_position,
            sample_period_s=float(
                getattr(config, "execution_motion_trace_sample_period_s", 0.05)
            ),
        )
    try:
        return robot_service.execute_trajectory(
            command_pivot_path,
            vel=vel,
            acc=acc,
            blocking=True,
            orientation_mode="per_waypoint",
        )
    finally:
        if trace is not None:
            samples = trace.stop()
            write_execution_motion_trace(
                debug_dump_dir=debug_dump_dir,
                pivot_config=pivot_config,
                commanded_path=command_pivot_path,
                actual_samples=samples,
                pivot_pose=list(pivot_pose) if pivot_pose is not None else None,
                pattern_type=pattern_type,
                stage=stage,
                tcp_to_tool_local_xy=tcp_to_tool_local_xy,
            )


def write_pivot_job_debug_artifacts(
    *,
    debug_dump_dir: str | None,
    pivot_config: PaintSimulationConfig,
    source_path: list[list[float]],
    command_pivot_path: list[list[float]],
    snapshots: list[np.ndarray] | None,
    diagnostics: list[dict[str, float | int]] | None,
    pivot_pose: list[float] | None,
    anchor_xy: tuple[float, float] | None,
    source_rotation_deg: float,
    pattern_type: str,
    stage: str,
    paint_process_config: PaintProcessConfig | None = None,
) -> None:
    config = paint_process_config or PAINT_PROCESS_CONFIG
    write_pivot_debug_dump(
        debug_dump_dir=debug_dump_dir,
        pivot_config=pivot_config,
        source_path=source_path,
        pivot_path=command_pivot_path,
        diagnostics=diagnostics,
        pivot_pose=list(pivot_pose) if pivot_pose is not None else None,
        anchor_xy=anchor_xy,
        source_rotation_deg=source_rotation_deg,
        pattern_type=pattern_type,
        stage=stage,
    )
    if config.enable_pivot_debug_plot:
        write_pivot_debug_plot(
            debug_dump_dir=debug_dump_dir,
            pivot_config=pivot_config,
            source_path=source_path,
            pivot_path=command_pivot_path,
            snapshots=snapshots,
            diagnostics=diagnostics,
            pivot_pose=list(pivot_pose) if pivot_pose is not None else None,
            pattern_type=pattern_type,
            stage=stage,
            anchor_xy=anchor_xy,
            source_rotation_deg=source_rotation_deg,
        )


from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
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
_CART_PATH_DIAG_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="cart_path_diag",
)


def elapsed_s(start: float) -> float:
    return perf_counter() - float(start)


def path_length_mm(path: list[list[float]]) -> float:
    xyz = np.asarray([pose[:3] for pose in path], dtype=float)
    if len(xyz) < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(xyz, axis=0), axis=1).sum())


def _log_cartesian_command_path_diagnostics(command_path: list[list[float]]) -> None:
    snapshot = [list(pose) for pose in command_path or []]
    _CART_PATH_DIAG_EXECUTOR.submit(
        _run_cartesian_command_path_diagnostics,
        snapshot,
    )


def _run_cartesian_command_path_diagnostics(command_path: list[list[float]]) -> None:
    try:
        _log_cartesian_command_path_diagnostics_sync(command_path)
    except Exception:
        _logger.debug("[CART_PATH_DIAG] background diagnostics failed", exc_info=True)


def _log_cartesian_command_path_diagnostics_sync(command_path: list[list[float]]) -> None:
    """Log final Cartesian command-path geometry without modifying the path.

    The goal is to distinguish an upstream Cartesian backtrack from an IK-only
    joint-space reversal.  Diagnostics run on the exact command path that will
    be handed to the robot service (including final orientation/retreat edits).
    """
    if not command_path:
        _logger.info("[CART_PATH_DIAG] points=0")
        return

    try:
        poses = np.asarray([pose[:6] for pose in command_path], dtype=float)
    except (TypeError, ValueError):
        _logger.warning("[CART_PATH_DIAG] unable to parse command path", exc_info=True)
        return

    if poses.ndim != 2 or poses.shape[0] == 0 or poses.shape[1] < 3:
        _logger.warning("[CART_PATH_DIAG] invalid command path shape=%s", poses.shape)
        return

    xyz = poses[:, :3]
    xyz_steps = np.diff(xyz, axis=0)
    xyz_step_norms = np.linalg.norm(xyz_steps, axis=1) if len(xyz_steps) else np.asarray([], dtype=float)
    near_duplicate_indices = [
        int(index)
        for index, norm in enumerate(xyz_step_norms)
        if float(norm) <= 1e-6
    ]

    xyz_spans = np.ptp(xyz, axis=0) if len(xyz) else np.zeros(3, dtype=float)
    max_xyz_step = float(np.max(xyz_step_norms)) if len(xyz_step_norms) else 0.0
    min_nonzero_xyz_step = (
        float(np.min(xyz_step_norms[xyz_step_norms > 1e-9]))
        if np.any(xyz_step_norms > 1e-9)
        else 0.0
    )

    rotation_summary = ""
    if poses.shape[1] >= 6:
        rotations = poses[:, 3:6]
        rotation_steps = np.diff(rotations, axis=0)
        max_rotation_step = (
            np.max(np.abs(rotation_steps), axis=0)
            if len(rotation_steps)
            else np.zeros(3, dtype=float)
        )
        rotation_summary = (
            f" max_rot_step_deg=[{max_rotation_step[0]:.6f},"
            f"{max_rotation_step[1]:.6f},{max_rotation_step[2]:.6f}]"
        )

    _logger.info(
        "[CART_PATH_DIAG] points=%d near_duplicate_xyz_segments=%d "
        "xyz_span_mm=[%.6f,%.6f,%.6f] min_nonzero_xyz_step_mm=%.9f "
        "max_xyz_step_mm=%.6f%s",
        len(command_path),
        len(near_duplicate_indices),
        float(xyz_spans[0]),
        float(xyz_spans[1]),
        float(xyz_spans[2]),
        min_nonzero_xyz_step,
        max_xyz_step,
        rotation_summary,
    )

    if near_duplicate_indices:
        _logger.warning(
            "[CART_PATH_DIAG] near_duplicate_xyz segment_starts=%s",
            near_duplicate_indices[:20],
        )

    if len(xyz) < 3:
        return

    candidates: list[tuple[float, int, float, float, float]] = []
    for middle in range(1, len(xyz) - 1):
        previous_step = xyz[middle] - xyz[middle - 1]
        next_step = xyz[middle + 1] - xyz[middle]
        previous_norm = float(np.linalg.norm(previous_step))
        next_norm = float(np.linalg.norm(next_step))
        if previous_norm <= 1e-9 or next_norm <= 1e-9:
            continue
        cosine = float(
            np.clip(
                np.dot(previous_step, next_step) / (previous_norm * next_norm),
                -1.0,
                1.0,
            )
        )
        angle_deg = float(np.degrees(np.arccos(cosine)))
        candidates.append((angle_deg, middle, cosine, previous_norm, next_norm))

    candidates.sort(key=lambda item: item[0], reverse=True)
    for rank, (angle_deg, middle, cosine, previous_norm, next_norm) in enumerate(candidates[:8], start=1):
        pose_prev = [round(float(value), 9) for value in poses[middle - 1].tolist()]
        pose_mid = [round(float(value), 9) for value in poses[middle].tolist()]
        pose_next = [round(float(value), 9) for value in poses[middle + 1].tolist()]
        xyz_prev_step = [round(float(value), 9) for value in (xyz[middle] - xyz[middle - 1]).tolist()]
        xyz_next_step = [round(float(value), 9) for value in (xyz[middle + 1] - xyz[middle]).tolist()]
        _logger.warning(
            "[CART_PATH_DIAG] reversal_candidate rank=%d middle=%d angle_deg=%.6f "
            "cos=%.9f prev_xyz_norm_mm=%.9f next_xyz_norm_mm=%.9f "
            "pose_prev=%s pose_mid=%s pose_next=%s dxyz_prev=%s dxyz_next=%s",
            rank,
            middle,
            angle_deg,
            cosine,
            previous_norm,
            next_norm,
            pose_prev,
            pose_mid,
            pose_next,
            xyz_prev_step,
            xyz_next_step,
        )

    near_180 = [item for item in candidates if item[0] >= 175.0]
    if near_180:
        worst = near_180[0]
        _logger.error(
            "[CART_PATH_DIAG] detected %d near-180deg XYZ reversal(s); "
            "worst_middle=%d worst_angle_deg=%.6f worst_cos=%.9f",
            len(near_180),
            int(worst[1]),
            float(worst[0]),
            float(worst[2]),
        )
    elif candidates:
        worst = candidates[0]
        _logger.info(
            "[CART_PATH_DIAG] no near-180deg XYZ reversal; "
            "worst_middle=%d worst_angle_deg=%.6f worst_cos=%.9f",
            int(worst[1]),
            float(worst[0]),
            float(worst[2]),
        )


def diagnostics_with_command_rotation(
    diagnostics: list[dict[str, float | int]] | None,
    command_path: list[list[float]],
    rotation_index: int,
) -> list[dict[str, float | int]] | None:
    """Attach final robot-command rotation values to projection diagnostics."""
    _log_cartesian_command_path_diagnostics(command_path)
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
    if config.enable_pivot_debug_plot:
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

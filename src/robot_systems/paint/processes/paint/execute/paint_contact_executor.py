from __future__ import annotations

import logging
from time import perf_counter
from typing import Callable

import numpy as np

from src.engine.geometry.planar import axis_equivalent_shift_degrees
from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import PaintSimulationConfig
from src.robot_systems.paint.processes.paint.execute.diagnostics import (
    diagnostics_with_command_rotation,
    elapsed_s,
    execute_paint_trajectory_with_optional_trace,
    path_length_mm,
    write_pivot_job_debug_artifacts,
)
from src.robot_systems.paint.processes.paint.execute.projection_preview import (
    pivot_source_path,
    projection_tool_anchor_xy,
)
from src.robot_systems.paint.timing import timed_block, timed_step

_logger = logging.getLogger(__name__)


def _shift_path_rotation(path: list[list[float]], rotation_index: int, shift_degrees: float) -> list[list[float]]:
    """Apply a constant shift to one rotation component across a projected path."""
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


def _tcp_to_tool_local_xy(job: dict, paint_config: PaintSimulationConfig) -> tuple[float, float] | None:
    """Return the local vector from configured robot TCP to selected tool point."""
    target_name = str(job.get("execution_target_point_name", "") or "").strip().lower()
    if not target_name or target_name == "camera":
        return None

    try:
        point_offset_x = float(job.get("execution_target_offset_x", 0.0) or 0.0)
        point_offset_y = float(job.get("execution_target_offset_y", 0.0) or 0.0)
        tcp_offset_x = float(paint_config.camera_to_tcp_x_offset)
        tcp_offset_y = float(paint_config.camera_to_tcp_y_offset)
    except (TypeError, ValueError):
        return None

    tcp_to_tool_x = point_offset_x - tcp_offset_x
    tcp_to_tool_y = point_offset_y - tcp_offset_y

    if abs(tcp_to_tool_x) <= 1e-9 and abs(tcp_to_tool_y) <= 1e-9:
        return None

    return tcp_to_tool_x, tcp_to_tool_y


def _append_retreat_opposite_to_staging(owner, command_path: list[list[float]]) -> list[list[float]]:
    """Append the existing retreat offset on the side opposite the paint-entry staging offset."""
    if not command_path:
        return []

    path_with_retreat = owner._append_contact_retreat_waypoint(command_path)
    if len(path_with_retreat) <= len(command_path):
        return path_with_retreat

    final_contact_pose = list(command_path[-1])
    retreat_pose = list(path_with_retreat[-1])

    try:
        config = owner._contact_motion_config
        axis_position = config.planar_axes.index(config.translation_axis)
        axis_index = config.planar_coordinate_indices[axis_position]
    except (AttributeError, ValueError, IndexError):
        _logger.warning(
            "[PIVOT_PATH] Could not resolve paint axis for opposite retreat; keeping existing retreat"
        )
        return path_with_retreat

    if len(final_contact_pose) <= axis_index or len(retreat_pose) <= axis_index:
        return path_with_retreat

    original_retreat_value = float(retreat_pose[axis_index])
    contact_value = float(final_contact_pose[axis_index])
    retreat_pose[axis_index] = 2.0 * contact_value - original_retreat_value
    path_with_retreat[-1] = retreat_pose

    _logger.info(
        "[PIVOT_PATH] flipped retreat opposite to staging side: axis=%s contact=%.3f old_retreat=%.3f new_retreat=%.3f",
        config.translation_axis,
        contact_value,
        original_retreat_value,
        float(retreat_pose[axis_index]),
    )
    return path_with_retreat


class PaintContactExecutor:
    """Execute prepared paint-contact paths against the fixed paint shaft."""

    def __init__(self, owner) -> None:
        self._owner = owner

    @timed_step(_logger, "execute_paint_contact_paths")
    def execute(
        self,
        execution_plan: WorkpieceExecutionPlan,
        *,
        vel_override: float | None = None,
        acc_override: float | None = None,
        append_retreat: bool = True,
        retreat_fn: Callable[[list[list[float]]], list[list[float]]] | None = None,
        execute_robot: bool = True,
        collected_command_paths: list[list[list[float]]] | None = None,
        collected_command_jobs: list[dict] | None = None,
        control=None,
    ) -> tuple[bool, str, int]:
        """Execute all projected paint-contact paths in the prepared execution plan."""
        owner = self._owner
        started = perf_counter()
        total_waypoints = 0
        with timed_block(_logger, "paint_contact_prepare", label="refresh_runtime_config"):
            owner._refresh_runtime_config()
        owner._last_process_start_rz = None
        owner._last_process_end_pose = None
        total_jobs = len(execution_plan.execution_jobs)
        for job_index, job in enumerate(execution_plan.execution_jobs, start=1):
            job_label = f"job_{job_index}"
            job_started = perf_counter()
            spline = pivot_source_path(job, owner._contact_motion_config)
            vel = float(vel_override) if vel_override is not None else float(job.get("vel", 10.0))
            acc = float(acc_override) if acc_override is not None else float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))
            pivot_offset_mm = owner._resolve_pivot_offset_mm(job, execution_plan)
            if not spline:
                continue

            anchor_xy = projection_tool_anchor_xy(job, owner._contact_motion_config)
            tcp_to_tool_local_xy = _tcp_to_tool_local_xy(job, owner._contact_motion_config)
            source_rotation_deg = (
                float(owner._last_pickup_plan.source_rotation_deg)
                if owner._last_pickup_plan is not None else 0.0
            )
            with timed_block(_logger, "paint_contact_job_prepare", label=f"{job_label}:build_execution_path"):
                if (
                    job_index == 1
                    and owner._last_pickup_plan is not None
                    and owner._contact_motion_config.motion_plane == owner._configured_contact_motion_plane
                    and owner._last_pickup_plan.projected_source_path is spline
                    and owner._last_pickup_plan.projected_pivot_path
                ):
                    pivot_path = [list(pose) for pose in owner._last_pickup_plan.projected_pivot_path]
                    snapshots = owner._last_pickup_plan.projected_snapshots
                    diagnostics = (
                        [dict(item) for item in owner._last_pickup_plan.projected_diagnostics]
                        if owner._last_pickup_plan.projected_diagnostics is not None else None
                    )
                    pivot_pose = list(owner._last_pickup_plan.paint_pivot_pose)
                    projected = (pivot_path, snapshots, diagnostics, pivot_pose)
                    _logger.info(
                        "[PAINT_CONTACT] Reusing pickup-stage projected path for %s: points=%d source_rotation_deg=%.3f",
                        job_label,
                        len(pivot_path),
                        source_rotation_deg,
                    )
                else:
                    projected = owner._build_paint_contact_path(
                        spline,
                        pivot_offset_mm=pivot_offset_mm,
                        align_start_to_zero_rz=False,
                        anchor_xy=anchor_xy,
                        source_rotation_deg=source_rotation_deg,
                    )
            if not projected:
                _logger.info(
                    "[TIMING] paint_contact_job index=%d pattern=%s success=false stage=build total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    elapsed_s(job_started),
                )
                return False, "Pickup succeeded, but paint-contact geometry could not be built", total_waypoints
            pivot_path, snapshots, diagnostics, pivot_pose = projected
            if not pivot_path:
                _logger.info(
                    "[TIMING] paint_contact_job index=%d pattern=%s success=false stage=build total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    elapsed_s(job_started),
                )
                return False, "Pickup succeeded, but paint-contact geometry could not be built", total_waypoints
            if (
                owner._contact_motion_config.motion_plane == "xz_y_ry"
                and owner._flip_xz_ry_execution_rotation_direction
                and pivot_path
            ):
                _logger.info(
                    "[PAINT_CONTACT] XZ/RY desired rotation direction was applied during projection; command path will not mirror RY afterward"
                )
            rotation_shift = 0.0
            rotation_index = owner._contact_motion_config.rotation_index
            if (
                owner._contact_motion_config.motion_plane == "xy_z_rz"
                and owner._last_pickup_plan is not None
                and pivot_path
                and len(pivot_path[0]) > rotation_index
                and len(owner._last_pickup_plan.staged_pose) > rotation_index
            ):
                staged_rotation = float(owner._last_pickup_plan.staged_pose[rotation_index])
                raw_start_rotation = float(pivot_path[0][rotation_index])
                rotation_shift = axis_equivalent_shift_degrees(staged_rotation, raw_start_rotation)
                if abs(rotation_shift) > 1e-9:
                    with timed_block(_logger, "paint_contact_job_prepare", label=f"{job_label}:shift_xy_rz_rotation"):
                        pivot_path = _shift_path_rotation(pivot_path, rotation_index, rotation_shift)
                    _logger.info(
                        "[PAINT_CONTACT] Applied xy/rz axis-equivalent path shift: staged_rz=%.3f raw_start_rz=%.3f shift=%.3f selected_start_rz=%.3f",
                        staged_rotation,
                        raw_start_rotation,
                        rotation_shift,
                        float(pivot_path[0][rotation_index]),
                    )
            if (
                owner._contact_motion_config.motion_plane == "xz_y_ry"
                and owner._last_pickup_plan is not None
                and pivot_path
                and len(pivot_path[0]) > rotation_index
                and len(owner._last_pickup_plan.staged_pose) > rotation_index
            ):
                staged_ry = float(owner._last_pickup_plan.staged_pose[rotation_index])
                raw_start_ry = float(pivot_path[0][rotation_index])
                rotation_shift = staged_ry - raw_start_ry
                if abs(rotation_shift) > 1e-9:
                    with timed_block(_logger, "paint_contact_job_prepare", label=f"{job_label}:shift_xz_ry_rotation"):
                        pivot_path = _shift_path_rotation(pivot_path, rotation_index, rotation_shift)
                    _logger.info(
                        "[PAINT_CONTACT] Applied xz/ry staging RY alignment shift: staged_ry=%.3f raw_start_ry=%.3f shift=%.3f selected_start_ry=%.3f",
                        staged_ry,
                        raw_start_ry,
                        rotation_shift,
                        float(pivot_path[0][rotation_index]),
                    )

            with timed_block(_logger, "paint_contact_job_prepare", label=f"{job_label}:build_command_path"):
                command_pivot_path = owner._paint_contact_command_path(pivot_path)
                if retreat_fn is not None:
                    command_pivot_path = retreat_fn(command_pivot_path)
                elif append_retreat:
                    command_pivot_path = _append_retreat_opposite_to_staging(owner, command_pivot_path)
            if owner._last_process_start_rz is None and command_pivot_path:
                owner._last_process_start_rz = float(command_pivot_path[0][5]) if len(command_pivot_path[0]) >= 6 else 0.0

            first_pose = [round(float(value), 3) for value in command_pivot_path[0][:6]]
            last_pose = [round(float(value), 3) for value in command_pivot_path[-1][:6]]
            _logger.info(
                "[PAINT_CONTACT] command_truth job=%d first_pose=%s last_pose=%s total_xyz_len_mm=%.3f",
                job_index,
                first_pose,
                last_pose,
                path_length_mm(command_pivot_path),
            )

            with timed_block(_logger, "paint_contact_job_debug", label=f"{job_label}:build_diagnostics"):
                if abs(rotation_shift) > 1e-9 and diagnostics is not None:
                    diagnostics = [dict(item) for item in diagnostics]
                    for item in diagnostics:
                        if "current_rz" in item:
                            item["current_rz"] = float(item["current_rz"]) + rotation_shift
                diagnostics = diagnostics_with_command_rotation(
                    diagnostics,
                    command_pivot_path,
                    rotation_index,
                )
            with timed_block(_logger, "paint_contact_job_debug", label=f"{job_label}:write_debug_dump"):
                write_pivot_job_debug_artifacts(
                    debug_dump_dir=owner._debug_dump_dir,
                    pivot_config=owner._contact_motion_config,
                    source_path=spline,
                    command_pivot_path=command_pivot_path,
                    snapshots=snapshots,
                    diagnostics=diagnostics,
                    pivot_pose=list(pivot_pose) if pivot_pose is not None else None,
                    anchor_xy=anchor_xy,
                    source_rotation_deg=source_rotation_deg,
                    pattern_type=pattern_type,
                    stage="execute",
                    paint_process_config=owner._paint_process_config(),
                )

            if collected_command_paths is not None:
                collected_command_paths.append([list(pose) for pose in command_pivot_path])
            if collected_command_jobs is not None:
                collected_command_jobs.append(
                    {
                        "job_index": job_index,
                        "pattern_type": pattern_type,
                        "vel": vel,
                        "acc": acc,
                    }
                )

            if not execute_robot:
                total_waypoints += len(command_pivot_path)
                owner._last_process_end_pose = list(command_pivot_path[-1])
                _logger.info(
                    "[TIMING] paint_contact_job index=%d pattern=%s success=true input_pts=%d output_pts=%d execute_skipped=true total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    len(spline),
                    len(command_pivot_path),
                    elapsed_s(job_started),
                )
                continue

            paint_pivot_config = owner._contact_motion_config
            if job_index == total_jobs:
                edge_cleanup = getattr(owner, "_edge_cleanup", None)
                start_preplanning = getattr(edge_cleanup, "start_preplanning_during_paint", None)
                if callable(start_preplanning):
                    start_preplanning(execution_plan, started=started)

            execute_started = perf_counter()
            with timed_block(_logger, "paint_contact_job_robot_execute", label=f"{job_label}:{pattern_type}"):
                protected_phase = getattr(control, "protected_phase", None)
                if callable(protected_phase):
                    with protected_phase():
                        result = execute_paint_trajectory_with_optional_trace(
                            robot_service=owner._robot_service,
                            debug_dump_dir=owner._debug_dump_dir,
                            pivot_config=paint_pivot_config,
                            command_pivot_path=command_pivot_path,
                            vel=vel,
                            acc=acc,
                            pivot_pose=pivot_pose,
                            pattern_type=pattern_type,
                            stage="execute",
                            tcp_to_tool_local_xy=tcp_to_tool_local_xy,
                            paint_process_config=owner._paint_process_config(),
                        )
                else:
                    result = execute_paint_trajectory_with_optional_trace(
                        robot_service=owner._robot_service,
                        debug_dump_dir=owner._debug_dump_dir,
                        pivot_config=paint_pivot_config,
                        command_pivot_path=command_pivot_path,
                        vel=vel,
                        acc=acc,
                        pivot_pose=pivot_pose,
                        pattern_type=pattern_type,
                        stage="execute",
                        tcp_to_tool_local_xy=tcp_to_tool_local_xy,
                        paint_process_config=owner._paint_process_config(),
                    )
            if result not in (0, True, None):
                _logger.info(
                    "[TIMING] paint_contact_job index=%d pattern=%s success=false input_pts=%d output_pts=%d execute_elapsed_s=%.3f total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    len(spline),
                    len(command_pivot_path),
                    elapsed_s(execute_started),
                    elapsed_s(job_started),
                )
                return False, f"Pickup succeeded, but {pattern_type} paint contact failed with code {result}", total_waypoints
            total_waypoints += len(command_pivot_path)
            owner._last_process_end_pose = list(command_pivot_path[-1])
            _logger.info(
                "[TIMING] paint_contact_job index=%d pattern=%s success=true input_pts=%d output_pts=%d execute_elapsed_s=%.3f total_elapsed_s=%.3f",
                job_index,
                pattern_type,
                len(spline),
                len(command_pivot_path),
                elapsed_s(execute_started),
                elapsed_s(job_started),
            )
            wait_if_paused = getattr(control, "wait_if_paused", None)
            if callable(wait_if_paused) and not wait_if_paused():
                return False, "Paint process stopped", total_waypoints
        _logger.info(
            "[TIMING] paint_contact_paths success=true jobs=%d total_waypoints=%d elapsed_s=%.3f",
            len(execution_plan.execution_jobs),
            total_waypoints,
            elapsed_s(started),
        )
        return True, "", total_waypoints

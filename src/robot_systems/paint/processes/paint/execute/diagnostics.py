from __future__ import annotations

import csv
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import re
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
_TRAJECTORY_EXPORT_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="platform_trajectory_export",
)


def elapsed_s(start: float) -> float:
    return perf_counter() - float(start)


def path_length_mm(path: list[list[float]]) -> float:
    xyz = np.asarray([pose[:3] for pose in path], dtype=float)
    if len(xyz) < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(xyz, axis=0), axis=1).sum())


def write_platform_command_path_csv(
    *,
    command_path: list[list[float]],
    vel: float,
    acc: float,
    pattern_type: str,
    stage: str,
    pipeline_stages: dict[str, list[list[float]]] | None = None,
):
    """Queue CSV and PNG export of the exact ROS-bound Cartesian path."""
    if not command_path:
        return None
    snapshot = tuple(tuple(float(value) for value in pose[:6]) for pose in command_path)
    pipeline_snapshot = {
        str(name): tuple(tuple(float(value) for value in point) for point in points)
        for name, points in (pipeline_stages or {}).items()
        if points
    }
    return _TRAJECTORY_EXPORT_EXECUTOR.submit(
        _write_platform_command_path_artifacts,
        snapshot,
        float(vel),
        float(acc),
        str(pattern_type),
        str(stage),
        pipeline_snapshot,
    )


def _write_platform_command_path_artifacts(
    command_path: tuple[tuple[float, ...], ...],
    vel: float,
    acc: float,
    pattern_type: str,
    stage: str,
    pipeline_stages,
) -> None:
    try:
        repository_root = Path(__file__).resolve().parents[6]
        output_dir = repository_root / "docs" / "trajectory_logs"
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{stage}_{pattern_type}").strip("_")
        timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
        stem = f"platform_pose_trajectory_{safe_label}_{timestamp}"
        output_path = output_dir / f"{stem}.csv"
        columns = ("x_mm", "y_mm", "z_mm", "rx_deg", "ry_deg", "rz_deg")
        with output_path.open("x", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(("point_index", *columns, "requested_velocity_percent", "requested_acceleration_percent"))
            for point_index, pose in enumerate(command_path):
                values = [
                    f"{float(pose[index]):.12g}" if index < len(pose) else ""
                    for index in range(6)
                ]
                writer.writerow((point_index, *values, f"{float(vel):.12g}", f"{float(acc):.12g}"))
        plot_path = output_dir / f"{stem}.png"
        _write_platform_pose_plot(plot_path, command_path)
        pipeline_csv_path = output_dir / f"{stem}_pipeline.csv"
        pipeline_plot_path = output_dir / f"{stem}_pipeline.png"
        before_after_plot_path = output_dir / f"{stem}_contour_before_after.png"
        _write_contour_pipeline_csv(pipeline_csv_path, pipeline_stages)
        _write_contour_pipeline_plot(pipeline_plot_path, pipeline_stages)
        _write_contour_before_after_plot(before_after_plot_path, pipeline_stages)
        _logger.info(
            "[PLATFORM_TRAJECTORY_EXPORT] wrote ROS-bound pose trajectory points=%d "
            "csv=%s plot=%s pipeline_csv=%s pipeline_plot=%s before_after_plot=%s",
            len(command_path),
            output_path,
            plot_path,
            pipeline_csv_path,
            pipeline_plot_path,
            before_after_plot_path,
        )
    except Exception:
        _logger.warning(
            "[PLATFORM_TRAJECTORY_EXPORT] background export failed without blocking motion",
            exc_info=True,
        )


def _write_contour_pipeline_csv(output_path: Path, pipeline_stages) -> None:
    with output_path.open("x", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(("stage", "point_index", "coordinate_space", "a", "b", "z", "rx", "ry", "rz"))
        for stage, points in pipeline_stages.items():
            coordinate_space = "px" if stage.endswith("_px") else "mm"
            for point_index, point in enumerate(points):
                padded = tuple(point) + ("",) * max(0, 6 - len(point))
                writer.writerow((stage, point_index, coordinate_space, *padded[:6]))


def _write_contour_pipeline_plot(output_path: Path, pipeline_stages) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(2, 2, figsize=(15, 11))
    pixel_axis, metric_axis, projected_axis, turn_axis = axes.ravel()
    for name, points in pipeline_stages.items():
        values = np.asarray(points, dtype=float)
        if values.ndim != 2 or len(values) < 2 or values.shape[1] < 2:
            continue
        if name.endswith("_px"):
            pixel_axis.plot(values[:, 0], values[:, 1], linewidth=1.0, label=f"{name} ({len(values)})")
        elif name in {"transformed_mm", "prepared_mm", "execution_mm"}:
            metric_axis.plot(values[:, 0], values[:, 1], linewidth=1.0, label=f"{name} ({len(values)})")
        elif name in {"projected_tcp_mm", "ros_command_mm"}:
            projected_axis.plot(values[:, 0], values[:, 1], linewidth=1.0, label=f"{name} ({len(values)})")

        turns = _path_turn_angles_degrees(values[:, :2])
        if len(turns):
            turn_axis.plot(np.arange(1, len(turns) + 1), turns, linewidth=0.9, label=name)

    pixel_axis.invert_yaxis()
    pixel_axis.set_title("Capture and pixel-space preparation")
    pixel_axis.set_xlabel("Image X [px]")
    pixel_axis.set_ylabel("Image Y [px]")
    metric_axis.set_title("Conversion and contour preparation")
    metric_axis.set_xlabel("X [mm]")
    metric_axis.set_ylabel("Y [mm]")
    projected_axis.set_title("RTCP projection and final ROS-bound command")
    projected_axis.set_xlabel("X [mm]")
    projected_axis.set_ylabel("Y [mm]")
    turn_axis.set_title("Local direction change introduced at each stage")
    turn_axis.set_xlabel("Middle point index")
    turn_axis.set_ylabel("Turn angle [deg]")
    turn_axis.axhline(90.0, color="darkorange", linestyle="--", linewidth=0.8)
    turn_axis.axhline(150.0, color="red", linestyle="--", linewidth=0.8)
    for axis in (pixel_axis, metric_axis, projected_axis):
        axis.set_aspect("equal", adjustable="datalim")
    for axis in axes.ravel():
        axis.grid(True, alpha=0.3)
        if axis.lines:
            axis.legend(loc="best", fontsize=8)
    figure.suptitle("Contour processing audit: capture to ROS 2 command")
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def _write_contour_before_after_plot(output_path: Path, pipeline_stages) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    before = np.asarray(pipeline_stages.get("rtcp_input_before_mm", ()), dtype=float)
    after = np.asarray(pipeline_stages.get("rtcp_input_smoothed_mm", ()), dtype=float)
    if before.ndim != 2 or after.ndim != 2 or len(before) < 2 or len(after) < 2:
        return

    count = min(len(before), len(after))
    displacement_mm = np.linalg.norm(after[:count, :2] - before[:count, :2], axis=1)
    figure, (path_axis, error_axis) = plt.subplots(1, 2, figsize=(15, 6))
    path_axis.plot(before[:, 0], before[:, 1], color="tab:blue", linewidth=1.5, label="before smoothing")
    path_axis.plot(after[:, 0], after[:, 1], color="tab:orange", linewidth=1.2, label="after smoothing")
    path_axis.set_aspect("equal", adjustable="datalim")
    path_axis.set_xlabel("X [mm]")
    path_axis.set_ylabel("Y [mm]")
    path_axis.set_title("RTCP input contour — equal physical scale")
    path_axis.grid(True, alpha=0.3)
    path_axis.legend(loc="best")

    error_axis.plot(np.arange(count), displacement_mm, color="tab:red", linewidth=1.0)
    error_axis.axhline(0.50, color="black", linestyle="--", linewidth=0.9, label="0.50 mm limit")
    error_axis.set_xlabel("Contour point index")
    error_axis.set_ylabel("Point displacement [mm]")
    error_axis.set_title(
        f"Smoothing displacement (max={float(np.max(displacement_mm)):.4f} mm)"
    )
    error_axis.grid(True, alpha=0.3)
    error_axis.legend(loc="best")
    figure.suptitle("Bounded contour smoothing before RTCP projection")
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def _path_turn_angles_degrees(xy: np.ndarray) -> np.ndarray:
    if len(xy) < 3:
        return np.asarray([], dtype=float)
    incoming = xy[1:-1] - xy[:-2]
    outgoing = xy[2:] - xy[1:-1]
    denominator = np.linalg.norm(incoming, axis=1) * np.linalg.norm(outgoing, axis=1)
    valid = denominator > 1e-12
    cosine = np.ones(len(incoming), dtype=float)
    cosine[valid] = np.einsum("ij,ij->i", incoming, outgoing)[valid] / denominator[valid]
    return np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))


def _write_platform_pose_plot(output_path: Path, command_path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    poses = np.asarray(command_path, dtype=float)
    xyz = poses[:, :3]
    indexes = np.arange(len(poses), dtype=int)
    step_mm = np.linalg.norm(np.diff(xyz, axis=0), axis=1)
    distance_mm = np.concatenate(([0.0], np.cumsum(step_mm)))
    detail_count = len(xyz)
    if len(step_mm) >= 2:
        typical_step_mm = float(np.median(step_mm[:-1]))
        if float(step_mm[-1]) > max(10.0, 10.0 * typical_step_mm):
            detail_count -= 1
    detail_xyz = xyz[:detail_count]
    detail_indexes = indexes[:detail_count]

    figure = plt.figure(figsize=(15, 10))
    spatial_axis = figure.add_subplot(2, 2, 1, projection="3d")
    xy_axis = figure.add_subplot(2, 2, 2)
    rotation_axis = figure.add_subplot(2, 2, 3)
    step_axis = figure.add_subplot(2, 2, 4)

    spatial_axis.plot(xyz[:, 0], xyz[:, 1], xyz[:, 2], color="tab:blue", linewidth=1.3)
    spatial_axis.scatter(xyz[:, 0], xyz[:, 1], xyz[:, 2], c=indexes, cmap="viridis", s=5)
    spatial_axis.scatter(*xyz[0], color="green", marker="o", s=55, label="start")
    spatial_axis.scatter(*xyz[-1], color="red", marker="x", s=65, label="end")
    spatial_axis.set_xlabel("X [mm]")
    spatial_axis.set_ylabel("Y [mm]")
    spatial_axis.set_zlabel("Z [mm]")
    spatial_axis.set_title("Cartesian path (colour = execution order)")
    spatial_axis.legend(loc="best")
    _set_equal_3d_axes(spatial_axis, xyz)

    xy_axis.plot(detail_xyz[:, 0], detail_xyz[:, 1], color="tab:blue", linewidth=1.3)
    xy_axis.scatter(
        detail_xyz[:, 0], detail_xyz[:, 1], c=detail_indexes, cmap="viridis", s=6
    )
    xy_axis.scatter(
        detail_xyz[0, 0], detail_xyz[0, 1], color="green", marker="o", s=55, label="start"
    )
    xy_axis.scatter(
        detail_xyz[-1, 0],
        detail_xyz[-1, 1],
        color="darkorange",
        marker="x",
        s=65,
        label="contour end",
    )
    xy_axis.set_xlabel("X [mm]")
    xy_axis.set_ylabel("Y [mm]")
    detail_suffix = " (final transition omitted)" if detail_count < len(xyz) else ""
    xy_axis.set_title(f"XY contour detail — equal physical scale{detail_suffix}")
    xy_axis.set_aspect("equal", adjustable="datalim")
    xy_axis.grid(True, alpha=0.3)
    xy_axis.legend(loc="best")

    for column, label in zip(range(3, 6), ("RX", "RY", "RZ")):
        if column < poses.shape[1]:
            rotation_axis.plot(distance_mm, poses[:, column], label=label, linewidth=1.2)
    rotation_axis.set_xlabel("Cumulative Cartesian distance [mm]")
    rotation_axis.set_ylabel("Commanded orientation [deg]")
    rotation_axis.set_title("Orientation along path")
    rotation_axis.grid(True, alpha=0.3)
    rotation_axis.legend(loc="best", ncol=3)

    step_axis.plot(indexes[1:], step_mm, color="tab:red", linewidth=1.0)
    step_axis.set_xlabel("Destination waypoint index")
    step_axis.set_ylabel("Cartesian step [mm]")
    step_axis.set_title("Distance between consecutive commands")
    step_axis.grid(True, alpha=0.3)

    figure.suptitle("Exact platform Cartesian command sent to ROS 2")
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def _set_equal_3d_axes(axis, xyz: np.ndarray) -> None:
    """Give X/Y/Z the same physical scale without collapsing flat paths."""
    minimum = np.min(xyz, axis=0)
    maximum = np.max(xyz, axis=0)
    center = (minimum + maximum) / 2.0
    radius = max(float(np.max(maximum - minimum)) / 2.0, 1.0)
    axis.set_xlim(center[0] - radius, center[0] + radius)
    axis.set_ylim(center[1] - radius, center[1] + radius)
    axis.set_zlim(center[2] - radius, center[2] + radius)
    axis.set_box_aspect((1.0, 1.0, 1.0))


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

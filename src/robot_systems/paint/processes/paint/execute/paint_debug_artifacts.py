from __future__ import annotations

import logging
import os
from datetime import datetime

import numpy as np

from src.engine.geometry.planar import rotate_xy_about, unwrap_degrees
from src.robot_systems.paint.processes.paint.config import PaintSimulationConfig
from src.robot_systems.paint.processes.paint.execute.execution_plane import (
    get_execution_plane_strategy,
)
from src.robot_systems.paint.processes.paint.execute.pivot_projection import (
    project_paint_motion_geometry,
)

_logger = logging.getLogger(__name__)


def _path_length_mm(path: list[list[float]]) -> float:
    if len(path) < 2:
        return 0.0
    total = 0.0
    for start_pose, end_pose in zip(path, path[1:]):
        total += float(np.linalg.norm(np.asarray(end_pose[:3], dtype=float) - np.asarray(start_pose[:3], dtype=float)))
    return total


def _axis_label_from_index(index: int) -> str:
    return {0: "X", 1: "Y", 2: "Z"}.get(int(index), f"Axis {index}")


def build_executed_snapshot_series(
    *,
    source_path: list[list[float]],
    executed_path: list[list[float]],
    pivot_pose: list[float] | None,
    pivot_config: PaintSimulationConfig,
) -> list[np.ndarray]:
    """Rebuild contour snapshots from the final executed pose sequence."""
    if not source_path or not executed_path or pivot_pose is None or len(pivot_pose) < 3:
        return []
    try:
        preview_path, preview_snapshots, _ = project_paint_motion_geometry(
            source_path,
            pivot_pose,
            pivot_config,
        )
        if not preview_path or not preview_snapshots:
            return []

        planar_i, planar_j = pivot_config.planar_coordinate_indices
        rotation_index = pivot_config.rotation_index
        pivot_xy = (float(pivot_pose[planar_i]), float(pivot_pose[planar_j]))
        reference_snapshot = np.asarray(preview_snapshots[0], dtype=float)
        reference_rotation = (
            float(preview_path[0][rotation_index]) if len(preview_path[0]) > rotation_index else 0.0
        )
        rebuilt_snapshots: list[np.ndarray] = []
        for pose in executed_path:
            target_rotation = float(pose[rotation_index]) if len(pose) > rotation_index else reference_rotation
            rotation_delta = unwrap_degrees(reference_rotation, target_rotation) - reference_rotation
            rotated_snapshot = np.asarray(
                [
                    rotate_xy_about(
                        (float(point[0]), float(point[1])),
                        rotation_delta,
                        pivot_xy,
                    )
                    for point in reference_snapshot
                ],
                dtype=float,
            )
            target_center = np.asarray(
                [
                    float(pose[planar_i]) if len(pose) > planar_i else 0.0,
                    float(pose[planar_j]) if len(pose) > planar_j else 0.0,
                ],
                dtype=float,
            )
            current_center = np.mean(rotated_snapshot, axis=0)
            rebuilt_snapshots.append(rotated_snapshot + (target_center - current_center))
        return rebuilt_snapshots
    except Exception:
        _logger.debug("[PIVOT] Failed to rebuild executed snapshots", exc_info=True)
        return []


def write_pivot_debug_dump(
    *,
    debug_dump_dir: str | None,
    pivot_config: PaintSimulationConfig,
    source_path: list[list[float]],
    pivot_path: list[list[float]],
    diagnostics: list[dict[str, float | int]] | None,
    pivot_pose: list[float] | None,
    pattern_type: str,
    stage: str,
) -> None:
    """Write source and projected pivot paths to disk for offline trajectory inspection."""
    if not debug_dump_dir:
        return

    try:
        os.makedirs(debug_dump_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_pattern = str(pattern_type or "path").strip().lower().replace(" ", "_")
        safe_stage = str(stage or "run").strip().lower().replace(" ", "_")
        safe_plane = str(pivot_config.motion_plane or "unknown").strip().lower()
        filepath = os.path.join(
            debug_dump_dir,
            f"pivot_trajectory_{safe_stage}_{safe_pattern}_{safe_plane}_{timestamp}.txt",
        )
        with open(filepath, "w", encoding="utf-8") as handle:
            handle.write(
                f"# Pivot trajectory dump\n"
                f"# timestamp={timestamp}\n"
                f"# pattern_type={pattern_type}\n"
                f"# stage={stage}\n"
                f"# motion_plane={pivot_config.motion_plane}\n"
                f"# translation_axis={pivot_config.translation_axis}\n"
                f"# paint_side={pivot_config.paint_side}\n"
                f"# translation_direction={pivot_config.translation_direction}\n"
                f"# source_count={len(source_path)}\n"
                f"# projected_count={len(pivot_path)}\n"
                f"# source_xyz_len_mm={_path_length_mm(source_path):.6f}\n"
                f"# projected_xyz_len_mm={_path_length_mm(pivot_path):.6f}\n"
            )
            if pivot_pose:
                pose_values = ", ".join(f"{float(value):.6f}" for value in pivot_pose)
                handle.write(f"# pivot_pose=[{pose_values}]\n")

            for section_name, path in (
                ("ORIGINAL_PLATFORM_PATH", source_path),
                ("PROJECTED_EXECUTION_PATH", pivot_path),
            ):
                handle.write(f"\n[{section_name}]\n")
                handle.write(f"count={len(path)}\n")
                for index, point in enumerate(path):
                    coords = ", ".join(f"{float(value):.6f}" for value in point)
                    handle.write(f"  {index:04d}: [{coords}]\n")
            if diagnostics:
                handle.write("\n[ROTATION_DIAGNOSTICS]\n")
                for entry in diagnostics:
                    handle.write(
                        "  {index:04d}: segment_length={segment_length:.6f}, "
                        "segment_heading={segment_heading:.6f}, "
                        "rotation_delta_raw={rotation_delta_raw:.6f}, "
                        "rotation_delta_applied={rotation_delta_applied:.6f}, "
                        "current_rz={current_rz:.6f}\n".format(
                            index=int(entry.get("index", 0)),
                            segment_length=float(entry.get("segment_length", 0.0)),
                            segment_heading=float(entry.get("segment_heading", 0.0)),
                            rotation_delta_raw=float(entry.get("rotation_delta_raw", 0.0)),
                            rotation_delta_applied=float(entry.get("rotation_delta_applied", 0.0)),
                            current_rz=float(entry.get("current_rz", 0.0)),
                        )
                    )
        _logger.info("[PIVOT] Wrote pivot trajectory debug dump to %s", filepath)
    except Exception:
        _logger.debug("[PIVOT] Failed to write pivot trajectory debug dump", exc_info=True)


def write_pivot_debug_plot(
    *,
    debug_dump_dir: str | None,
    pivot_config: PaintSimulationConfig,
    source_path: list[list[float]],
    pivot_path: list[list[float]],
    snapshots: list[np.ndarray] | None,
    diagnostics: list[dict[str, float | int]] | None,
    pivot_pose: list[float] | None,
    pattern_type: str,
    stage: str,
) -> None:
    """Write a compact visual debug plot for the source and projected pivot trajectories."""
    if not debug_dump_dir or not source_path or not pivot_path:
        return

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        os.makedirs(debug_dump_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_pattern = str(pattern_type or "path").strip().lower().replace(" ", "_")
        safe_stage = str(stage or "run").strip().lower().replace(" ", "_")
        safe_plane = str(pivot_config.motion_plane or "unknown").strip().lower()
        filepath = os.path.join(
            debug_dump_dir,
            f"pivot_trajectory_{safe_stage}_{safe_pattern}_{safe_plane}_{timestamp}.png",
        )

        planar_i, planar_j = pivot_config.planar_coordinate_indices
        source_i, source_j = pivot_config.source_planar_coordinate_indices
        rotation_index = pivot_config.rotation_index

        source_xy = np.asarray([[float(p[source_i]), float(p[source_j])] for p in source_path], dtype=float)
        projected_xy = np.asarray([[float(p[planar_i]), float(p[planar_j])] for p in pivot_path], dtype=float)
        projected_rot = np.asarray(
            [float(p[rotation_index]) if len(p) > rotation_index else 0.0 for p in pivot_path],
            dtype=float,
        )
        snapshot_list = [
            np.asarray(snapshot, dtype=float)
            for snapshot in build_executed_snapshot_series(
                source_path=source_path,
                executed_path=pivot_path,
                pivot_pose=pivot_pose,
                pivot_config=pivot_config,
            ) or (snapshots or [])
            if len(snapshot) >= 1
        ]
        waypoint_idx = np.arange(len(pivot_path), dtype=float)
        rotation_delta = np.asarray(
            [float(entry.get("rotation_delta_applied", 0.0)) for entry in (diagnostics or [])],
            dtype=float,
        )
        if rotation_delta.size < len(pivot_path):
            rotation_delta = np.pad(
                rotation_delta,
                (0, len(pivot_path) - rotation_delta.size),
                mode="constant",
                constant_values=0.0,
            )

        if snapshot_list:
            highlighted_indices = [0]
            if len(snapshot_list) >= 2:
                highlighted_indices.append(1)
            sample_count = min(8, len(snapshot_list))
            sample_indices = np.unique(
                np.round(np.linspace(0, len(snapshot_list) - 1, sample_count)).astype(int)
            )
            sample_indices = np.unique(np.asarray([*highlighted_indices, *sample_indices], dtype=int))
            snapshot_rows = int(np.ceil(len(sample_indices) / 3))
            fig = plt.figure(figsize=(18, 6 + (3.2 * snapshot_rows)), constrained_layout=True)
            grid = fig.add_gridspec(1 + snapshot_rows, 3)
            ax_source = fig.add_subplot(grid[0, 0])
            ax_projected = fig.add_subplot(grid[0, 1:])
            snapshot_axes = [
                fig.add_subplot(grid[1 + (idx // 3), idx % 3])
                for idx in range(len(sample_indices))
            ]
        else:
            fig, axes = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
            ax_source = axes[0]
            ax_projected = axes[1]
            snapshot_axes = [axes[2]]
            sample_indices = np.asarray([], dtype=int)

        fig.suptitle(f"Pivot Trajectory Debug: {pattern_type} [{pivot_config.motion_plane}]", fontsize=12)

        arrow_step = max(1, len(source_xy) // 12)
        ax_source.plot(source_xy[:, 0], source_xy[:, 1], color="#1f77b4", linewidth=1.5)
        ax_source.scatter(source_xy[0, 0], source_xy[0, 1], color="green", s=40, label="start")
        ax_source.scatter(source_xy[-1, 0], source_xy[-1, 1], color="red", s=40, label="end")
        ax_source.quiver(
            source_xy[:-1:arrow_step, 0],
            source_xy[:-1:arrow_step, 1],
            source_xy[1::arrow_step, 0] - source_xy[:-1:arrow_step, 0],
            source_xy[1::arrow_step, 1] - source_xy[:-1:arrow_step, 1],
            angles="xy",
            scale_units="xy",
            scale=1.0,
            width=0.003,
            color="#1f77b4",
            alpha=0.75,
        )
        ax_source.set_title("Source Path")
        ax_source.set_xlabel(f"Source Axis {source_i}")
        ax_source.set_ylabel(f"Source Axis {source_j}")
        ax_source.axis("equal")
        ax_source.grid(True, alpha=0.25)
        ax_source.legend(loc="best")

        scatter = ax_projected.scatter(projected_xy[:, 0], projected_xy[:, 1], c=waypoint_idx, cmap="viridis", s=18)
        ax_projected.plot(projected_xy[:, 0], projected_xy[:, 1], color="#444444", linewidth=1.0, alpha=0.8)
        ax_projected.scatter(projected_xy[0, 0], projected_xy[0, 1], color="green", s=40, label="start")
        ax_projected.scatter(projected_xy[-1, 0], projected_xy[-1, 1], color="red", s=40, label="end")
        if len(projected_xy) >= 2:
            ax_projected.annotate(
                "",
                xy=(projected_xy[1, 0], projected_xy[1, 1]),
                xytext=(projected_xy[0, 0], projected_xy[0, 1]),
                arrowprops=dict(arrowstyle="->", color="#d62728", lw=2.0),
            )
            ax_projected.text(projected_xy[0, 0], projected_xy[0, 1], " contact", color="#d62728", fontsize=8)
            ax_projected.text(projected_xy[1, 0], projected_xy[1, 1], " first move", color="#d62728", fontsize=8)
        ax_projected.quiver(
            projected_xy[:-1:arrow_step, 0],
            projected_xy[:-1:arrow_step, 1],
            projected_xy[1::arrow_step, 0] - projected_xy[:-1:arrow_step, 0],
            projected_xy[1::arrow_step, 1] - projected_xy[:-1:arrow_step, 1],
            angles="xy",
            scale_units="xy",
            scale=1.0,
            width=0.003,
            color="#444444",
            alpha=0.65,
        )
        if pivot_pose is not None and len(pivot_pose) > max(planar_i, planar_j):
            ax_projected.scatter(
                float(pivot_pose[planar_i]),
                float(pivot_pose[planar_j]),
                color="orange",
                s=55,
                marker="x",
                label="pivot",
            )
        ax_projected.set_title("Projected Execution Path")
        ax_projected.set_xlabel(_axis_label_from_index(planar_i))
        ax_projected.set_ylabel(_axis_label_from_index(planar_j))
        ax_projected.axis("equal")
        ax_projected.grid(True, alpha=0.25)
        ax_projected.legend(loc="best")
        fig.colorbar(scatter, ax=ax_projected, fraction=0.046, pad=0.04, label="waypoint")

        if snapshot_list:
            snapshot_cmap = plt.get_cmap("viridis")
            sampled_snapshots = [snapshot_list[int(sample_index)] for sample_index in sample_indices]
            min_x = min(float(np.min(snapshot[:, 0])) for snapshot in sampled_snapshots)
            max_x = max(float(np.max(snapshot[:, 0])) for snapshot in sampled_snapshots)
            min_y = min(float(np.min(snapshot[:, 1])) for snapshot in sampled_snapshots)
            max_y = max(float(np.max(snapshot[:, 1])) for snapshot in sampled_snapshots)
            if pivot_pose is not None and len(pivot_pose) > max(planar_i, planar_j):
                pivot_x = float(pivot_pose[planar_i])
                pivot_y = float(pivot_pose[planar_j])
                min_x = min(min_x, pivot_x)
                max_x = max(max_x, pivot_x)
                min_y = min(min_y, pivot_y)
                max_y = max(max_y, pivot_y)
            pad_x = max(10.0, (max_x - min_x) * 0.08)
            pad_y = max(10.0, (max_y - min_y) * 0.08)

            for draw_order, sample_index in enumerate(sample_indices):
                snapshot = snapshot_list[int(sample_index)]
                color = snapshot_cmap(0.0 if len(sample_indices) == 1 else draw_order / (len(sample_indices) - 1))
                is_contact = int(sample_index) == 0
                is_first_move = int(sample_index) == 1
                line_width = 2.6 if (is_contact or is_first_move) else 1.2
                line_style = "-" if is_contact else ("--" if is_first_move else "-")
                ax_snapshot = snapshot_axes[draw_order]
                ax_snapshot.plot(snapshot[:, 0], snapshot[:, 1], color=color, linewidth=line_width, linestyle=line_style, alpha=0.95)
                ax_snapshot.scatter(snapshot[0, 0], snapshot[0, 1], color=color, s=42 if (is_contact or is_first_move) else 18, alpha=0.95)
                if len(snapshot) >= 2:
                    ax_snapshot.plot(
                        snapshot[:2, 0],
                        snapshot[:2, 1],
                        color="#d62728" if is_contact else "#ff7f0e" if is_first_move else color,
                        linewidth=3.0 if (is_contact or is_first_move) else line_width,
                        alpha=0.9,
                    )
                if int(sample_index) < len(projected_xy):
                    tcp_x = float(projected_xy[int(sample_index), 0])
                    tcp_y = float(projected_xy[int(sample_index), 1])
                    ax_snapshot.scatter(tcp_x, tcp_y, color="#d62728", s=28, marker="o", label="executed tcp", zorder=5)
                if pivot_pose is not None and len(pivot_pose) > max(planar_i, planar_j):
                    pivot_xy = np.asarray([float(pivot_pose[planar_i]), float(pivot_pose[planar_j])], dtype=float)
                    nearest_index = int(np.argmin(np.linalg.norm(snapshot - pivot_xy, axis=1)))
                    nearest_point = snapshot[nearest_index]
                    ax_snapshot.scatter(float(nearest_point[0]), float(nearest_point[1]), color="#ff7f0e", s=24, marker="s", label="nearest to pivot", zorder=5)
                label = f"Step {int(sample_index)}"
                if is_contact:
                    label = "Step 0 - contact"
                elif is_first_move:
                    label = "Step 1 - first move"
                ax_snapshot.set_title(label)
                if pivot_pose is not None and len(pivot_pose) > max(planar_i, planar_j):
                    ax_snapshot.scatter(float(pivot_pose[planar_i]), float(pivot_pose[planar_j]), color="orange", s=55, marker="x", label="pivot")
                ax_snapshot.set_xlim(min_x - pad_x, max_x + pad_x)
                ax_snapshot.set_ylim(min_y - pad_y, max_y + pad_y)
                ax_snapshot.set_xlabel(_axis_label_from_index(planar_i))
                ax_snapshot.set_ylabel(_axis_label_from_index(planar_j))
                ax_snapshot.axis("equal")
                ax_snapshot.grid(True, alpha=0.25)
                if pivot_pose is not None and len(pivot_pose) > max(planar_i, planar_j):
                    ax_snapshot.legend(loc="best")

            for empty_index in range(len(sample_indices), len(snapshot_axes)):
                snapshot_axes[empty_index].axis("off")

            if snapshot_axes:
                snapshot_axes[0].text(
                    0.02,
                    1.08,
                    "Executed Workpiece Snapshots (one subplot per sampled step)",
                    transform=snapshot_axes[0].transAxes,
                    fontsize=10,
                    fontweight="bold",
                    ha="left",
                )
        else:
            ax_rotation = snapshot_axes[0]
            ax_rotation.plot(waypoint_idx, projected_rot, color="#d62728", linewidth=1.5, label="active rotation")
            ax_rotation.bar(waypoint_idx, rotation_delta[: len(waypoint_idx)], color="#9467bd", alpha=0.35, width=0.8, label="rotation delta")
            ax_rotation.axhline(0.0, color="#666666", linewidth=0.8, alpha=0.6)
            ax_rotation.set_title("Rotation Progression")
            ax_rotation.set_xlabel("Waypoint")
            ax_rotation.set_ylabel(
                f"{get_execution_plane_strategy(pivot_config.motion_plane).rotation_axis_label} (deg)"
            )
            ax_rotation.grid(True, alpha=0.25)
            ax_rotation.legend(loc="best")

        fig.text(
            0.5,
            0.01,
            (
                f"source_xyz_len={_path_length_mm(source_path):.1f} mm   "
                f"projected_xyz_len={_path_length_mm(pivot_path):.1f} mm   "
                f"translation_axis={pivot_config.translation_axis}   "
                f"plane={pivot_config.motion_plane}"
            ),
            ha="center",
            fontsize=9,
        )
        fig.savefig(filepath, dpi=180)
        plt.close(fig)
        _logger.info("[PIVOT] Wrote pivot trajectory debug plot to %s", filepath)
    except Exception:
        _logger.debug("[PIVOT] Failed to write pivot trajectory debug plot", exc_info=True)

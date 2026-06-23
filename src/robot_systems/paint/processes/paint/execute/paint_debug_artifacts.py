from __future__ import annotations

import logging
import json
import os
from datetime import datetime
from threading import Event, Thread
from time import perf_counter
from typing import Callable, Sequence

import numpy as np
from src.engine.robot.targeting.target_point_geometry import rotate_offset_xyz
from src.robot_systems.paint.processes.paint.config import PaintSimulationConfig
from src.robot_systems.paint.processes.paint.execute.execution_plane import (
    get_execution_plane_strategy,
)
from src.robot_systems.paint.processes.paint.execute.pivot_projection import (
    project_paint_motion_geometry_continuous,
)

_logger = logging.getLogger(__name__)


class RobotMotionTrace:
    """Background sampler for actual robot poses during blocking trajectory execution."""

    def __init__(
        self,
        *,
        get_pose: Callable[[], Sequence[float] | None],
        sample_period_s: float,
    ) -> None:
        self._get_pose = get_pose
        self._sample_period_s = max(0.01, float(sample_period_s))
        self._stop = Event()
        self._samples: list[dict[str, object]] = []
        self._started_at = perf_counter()
        self._thread = Thread(target=self._run, name="paint-motion-trace", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> list[dict[str, object]]:
        self._stop.set()
        self._thread.join(timeout=max(1.0, self._sample_period_s * 4.0))
        return list(self._samples)

    def _run(self) -> None:
        while not self._stop.is_set():
            timestamp_s = perf_counter() - self._started_at
            try:
                pose = self._get_pose()
                if pose is not None and len(pose) >= 6:
                    self._samples.append(
                        {
                            "t_s": timestamp_s,
                            "pose": [float(pose[index]) for index in range(6)],
                        }
                    )
            except Exception as exc:
                self._samples.append({"t_s": timestamp_s, "error": str(exc)})
            self._stop.wait(self._sample_period_s)


def start_robot_motion_trace(
    *,
    get_pose: Callable[[], Sequence[float] | None],
    sample_period_s: float,
) -> RobotMotionTrace:
    trace = RobotMotionTrace(get_pose=get_pose, sample_period_s=sample_period_s)
    trace.start()
    return trace


def _path_length_mm(path: list[list[float]]) -> float:
    if len(path) < 2:
        return 0.0
    total = 0.0
    for start_pose, end_pose in zip(path, path[1:]):
        total += float(np.linalg.norm(np.asarray(end_pose[:3], dtype=float) - np.asarray(start_pose[:3], dtype=float)))
    return total


def _axis_label_from_index(index: int) -> str:
    return {0: "X", 1: "Y", 2: "Z"}.get(int(index), f"Axis {index}")


def _unwrap_degrees(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    return np.degrees(np.unwrap(np.radians(values.astype(float))))


def _angle_delta_deg(value: float, reference: float) -> float:
    return float((float(value) - float(reference) + 180.0) % 360.0 - 180.0)


def _motion_trace_comparison(
    *,
    commanded_path: list[list[float]],
    actual_samples: list[dict[str, object]],
    pivot_config: PaintSimulationConfig,
    pivot_pose: list[float] | None,
    tcp_to_tool_local_xy: tuple[float, float] | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    if not commanded_path:
        return {"sample_count": len(actual_samples), "command_count": 0}, []

    planar_i, planar_j = pivot_config.planar_coordinate_indices
    rotation_index = pivot_config.rotation_index
    required_index = max(planar_i, planar_j, rotation_index)
    command_valid = [pose for pose in commanded_path if len(pose) > required_index]
    if not command_valid:
        return {"sample_count": len(actual_samples), "command_count": len(commanded_path)}, []

    command_planar = np.asarray(
        [[float(pose[planar_i]), float(pose[planar_j])] for pose in command_valid],
        dtype=float,
    )
    command_rot = _unwrap_degrees(np.asarray([float(pose[rotation_index]) for pose in command_valid], dtype=float))
    command_step = np.linalg.norm(np.diff(command_planar, axis=0), axis=1)
    command_s = np.concatenate(([0.0], np.cumsum(command_step)))
    command_total_s = float(command_s[-1]) if command_s.size else 0.0

    pivot_planar = None
    if pivot_pose is not None and len(pivot_pose) > max(planar_i, planar_j):
        pivot_planar = np.asarray([float(pivot_pose[planar_i]), float(pivot_pose[planar_j])], dtype=float)

    def _tool_pose_from_tcp_pose(pose: list[float]) -> list[float] | None:
        if tcp_to_tool_local_xy is None or len(pose) < 6:
            return None
        offset_x, offset_y, offset_z = rotate_offset_xyz(
            float(tcp_to_tool_local_xy[0]),
            float(tcp_to_tool_local_xy[1]),
            0.0,
            rx_degrees=float(pose[3]),
            ry_degrees=float(pose[4]),
            rz_degrees=float(pose[5]),
        )
        tool_pose = list(pose[:6])
        tool_pose[0] = float(pose[0]) + offset_x
        tool_pose[1] = float(pose[1]) + offset_y
        tool_pose[2] = float(pose[2]) + offset_z
        return tool_pose

    comparisons: list[dict[str, object]] = []
    actual_pose_rows: list[tuple[dict[str, object], list[float]]] = []
    for sample in actual_samples:
        raw_pose = sample.get("pose")
        if not isinstance(raw_pose, list) or len(raw_pose) <= required_index:
            continue
        try:
            pose = [float(raw_pose[index]) for index in range(6)]
        except (TypeError, ValueError):
            continue
        actual_pose_rows.append((sample, pose))

    if not actual_pose_rows:
        return {
            "sample_count": len(actual_samples),
            "valid_sample_count": 0,
            "command_count": len(command_valid),
        }, []

    actual_rot = _unwrap_degrees(np.asarray([pose[rotation_index] for _, pose in actual_pose_rows], dtype=float))
    for sample_index, (sample, pose) in enumerate(actual_pose_rows):
        actual_xy = np.asarray([pose[planar_i], pose[planar_j]], dtype=float)
        planar_distances = np.linalg.norm(command_planar - actual_xy, axis=1)
        nearest_planar_index = int(np.argmin(planar_distances))
        rotation_distances = np.abs(command_rot - actual_rot[sample_index])
        nearest_rotation_index = int(np.argmin(rotation_distances))
        command_at_planar = command_valid[nearest_planar_index]
        command_planar_rot = float(command_rot[nearest_planar_index])
        actual_rot_value = float(actual_rot[sample_index])

        row: dict[str, object] = {
            "sample_index": sample_index,
            "t_s": float(sample.get("t_s", 0.0)),
            "actual_pose": pose,
            "nearest_planar_command_index": nearest_planar_index,
            "nearest_rotation_command_index": nearest_rotation_index,
            "phase_index_delta": int(nearest_rotation_index - nearest_planar_index),
            "command_progress_at_planar": (
                float(command_s[nearest_planar_index] / command_total_s)
                if command_total_s > 1e-9 else 0.0
            ),
            "planar_error_mm": float(planar_distances[nearest_planar_index]),
            "rotation_error_at_nearest_planar_deg": _angle_delta_deg(actual_rot_value, command_planar_rot),
            "command_pose_at_nearest_planar": [float(value) for value in command_at_planar[:6]],
        }
        if pivot_planar is not None:
            actual_radius = float(np.linalg.norm(actual_xy - pivot_planar))
            command_radius = float(np.linalg.norm(command_planar[nearest_planar_index] - pivot_planar))
            row["actual_pivot_radius_mm"] = actual_radius
            row["command_pivot_radius_at_nearest_planar_mm"] = command_radius
            row["pivot_radius_error_mm"] = actual_radius - command_radius
        actual_tool_pose = _tool_pose_from_tcp_pose(pose)
        command_tool_pose = _tool_pose_from_tcp_pose(list(command_at_planar[:6]))
        if actual_tool_pose is not None and command_tool_pose is not None:
            actual_tool_planar = np.asarray(
                [actual_tool_pose[planar_i], actual_tool_pose[planar_j]],
                dtype=float,
            )
            command_tool_planar = np.asarray(
                [command_tool_pose[planar_i], command_tool_pose[planar_j]],
                dtype=float,
            )
            row["actual_tool_pose"] = [float(value) for value in actual_tool_pose[:6]]
            row["command_tool_pose_at_nearest_planar"] = [
                float(value) for value in command_tool_pose[:6]
            ]
            row["tool_planar_error_mm"] = float(
                np.linalg.norm(actual_tool_planar - command_tool_planar)
            )
            if pivot_planar is not None:
                actual_tool_radius = float(np.linalg.norm(actual_tool_planar - pivot_planar))
                command_tool_radius = float(np.linalg.norm(command_tool_planar - pivot_planar))
                row["actual_tool_pivot_radius_mm"] = actual_tool_radius
                row["command_tool_pivot_radius_at_nearest_planar_mm"] = command_tool_radius
                row["tool_pivot_radius_error_mm"] = actual_tool_radius - command_tool_radius
        comparisons.append(row)

    planar_errors = np.asarray([float(row["planar_error_mm"]) for row in comparisons], dtype=float)
    rotation_errors = np.asarray(
        [abs(float(row["rotation_error_at_nearest_planar_deg"])) for row in comparisons],
        dtype=float,
    )
    phase_deltas = np.asarray([int(row["phase_index_delta"]) for row in comparisons], dtype=float)
    radius_errors = np.asarray(
        [float(row.get("pivot_radius_error_mm", 0.0)) for row in comparisons if "pivot_radius_error_mm" in row],
        dtype=float,
    )
    tool_planar_errors = np.asarray(
        [
            float(row.get("tool_planar_error_mm", 0.0))
            for row in comparisons
            if "tool_planar_error_mm" in row
        ],
        dtype=float,
    )
    tool_radius_errors = np.asarray(
        [
            float(row.get("tool_pivot_radius_error_mm", 0.0))
            for row in comparisons
            if "tool_pivot_radius_error_mm" in row
        ],
        dtype=float,
    )
    actual_tool_radii = np.asarray(
        [
            float(row.get("actual_tool_pivot_radius_mm", 0.0))
            for row in comparisons
            if "actual_tool_pivot_radius_mm" in row
        ],
        dtype=float,
    )
    summary: dict[str, object] = {
        "sample_count": len(actual_samples),
        "valid_sample_count": len(comparisons),
        "command_count": len(command_valid),
        "command_planar_length_mm": command_total_s,
        "max_planar_error_mm": float(np.max(planar_errors)) if planar_errors.size else 0.0,
        "mean_planar_error_mm": float(np.mean(planar_errors)) if planar_errors.size else 0.0,
        "max_rotation_error_at_nearest_planar_deg": float(np.max(rotation_errors)) if rotation_errors.size else 0.0,
        "mean_rotation_error_at_nearest_planar_deg": float(np.mean(rotation_errors)) if rotation_errors.size else 0.0,
        "max_abs_phase_index_delta": int(np.max(np.abs(phase_deltas))) if phase_deltas.size else 0,
        "mean_phase_index_delta": float(np.mean(phase_deltas)) if phase_deltas.size else 0.0,
    }
    if radius_errors.size:
        summary.update(
            {
                "max_abs_pivot_radius_error_mm": float(np.max(np.abs(radius_errors))),
                "mean_pivot_radius_error_mm": float(np.mean(radius_errors)),
            }
        )
    if tcp_to_tool_local_xy is not None:
        summary["tcp_to_tool_local_xy"] = [
            float(tcp_to_tool_local_xy[0]),
            float(tcp_to_tool_local_xy[1]),
        ]
    if tool_planar_errors.size:
        summary.update(
            {
                "max_tool_planar_error_mm": float(np.max(tool_planar_errors)),
                "mean_tool_planar_error_mm": float(np.mean(tool_planar_errors)),
            }
        )
    if tool_radius_errors.size:
        summary.update(
            {
                "max_abs_tool_pivot_radius_error_mm": float(np.max(np.abs(tool_radius_errors))),
                "mean_tool_pivot_radius_error_mm": float(np.mean(tool_radius_errors)),
            }
        )
    if actual_tool_radii.size:
        summary.update(
            {
                "min_actual_tool_pivot_radius_mm": float(np.min(actual_tool_radii)),
                "max_actual_tool_pivot_radius_mm": float(np.max(actual_tool_radii)),
                "mean_actual_tool_pivot_radius_mm": float(np.mean(actual_tool_radii)),
            }
        )
    return summary, comparisons


def write_execution_motion_trace(
    *,
    debug_dump_dir: str | None,
    pivot_config: PaintSimulationConfig,
    commanded_path: list[list[float]],
    actual_samples: list[dict[str, object]],
    pivot_pose: list[float] | None,
    pattern_type: str,
    stage: str,
    tcp_to_tool_local_xy: tuple[float, float] | None = None,
) -> None:
    """Write commanded-vs-actual robot motion samples for execution diagnostics."""
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
            f"execution_motion_trace_{safe_stage}_{safe_pattern}_{safe_plane}_{timestamp}.json",
        )
        summary, comparisons = _motion_trace_comparison(
            commanded_path=commanded_path,
            actual_samples=actual_samples,
            pivot_config=pivot_config,
            pivot_pose=pivot_pose,
            tcp_to_tool_local_xy=tcp_to_tool_local_xy,
        )
        payload = {
            "timestamp": timestamp,
            "pattern_type": pattern_type,
            "stage": stage,
            "motion_plane": pivot_config.motion_plane,
            "planar_coordinate_indices": list(pivot_config.planar_coordinate_indices),
            "rotation_index": pivot_config.rotation_index,
            "pivot_pose": [float(value) for value in pivot_pose] if pivot_pose is not None else None,
            "tcp_to_tool_local_xy": (
                [float(tcp_to_tool_local_xy[0]), float(tcp_to_tool_local_xy[1])]
                if tcp_to_tool_local_xy is not None else None
            ),
            "summary": summary,
            "commanded_path": [[float(value) for value in pose[:6]] for pose in commanded_path],
            "actual_samples": actual_samples,
            "comparisons": comparisons,
        }
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        _logger.info("[PIVOT] Wrote execution motion trace to %s", filepath)
    except Exception:
        _logger.debug("[PIVOT] Failed to write execution motion trace", exc_info=True)


def build_executed_snapshot_series(
    *,
    source_path: list[list[float]],
    executed_path: list[list[float]],
    pivot_pose: list[float] | None,
    pivot_config: PaintSimulationConfig,
    anchor_xy: tuple[float, float] | None = None,
    source_rotation_deg: float = 0.0,
) -> list[np.ndarray]:
    """Rebase projected physical contour snapshots onto the final robot command poses."""
    if not source_path or not executed_path or pivot_pose is None or len(pivot_pose) < 3:
        return []
    try:
        if anchor_xy is None:
            preview_path, preview_snapshots, _ = project_paint_motion_geometry_continuous(
                source_path,
                pivot_pose,
                pivot_config,
                source_rotation_deg=source_rotation_deg,
            )
        else:
            preview_path, preview_snapshots, _ = project_paint_motion_geometry_continuous(
                source_path,
                pivot_pose,
                pivot_config,
                anchor_xy=anchor_xy,
                source_rotation_deg=source_rotation_deg,
            )
        if not preview_path or not preview_snapshots:
            return []

        planar_i, planar_j = pivot_config.planar_coordinate_indices
        rebuilt_snapshots: list[np.ndarray] = []
        for index, pose in enumerate(executed_path):
            preview_index = min(index, len(preview_snapshots) - 1, len(preview_path) - 1)
            snapshot = np.asarray(preview_snapshots[preview_index], dtype=float)
            preview_pose = preview_path[preview_index]
            preview_anchor = np.asarray(
                [
                    float(preview_pose[planar_i]) if len(preview_pose) > planar_i else 0.0,
                    float(preview_pose[planar_j]) if len(preview_pose) > planar_j else 0.0,
                ],
                dtype=float,
            )
            target_anchor = np.asarray(
                [
                    float(pose[planar_i]) if len(pose) > planar_i else 0.0,
                    float(pose[planar_j]) if len(pose) > planar_j else 0.0,
                ],
                dtype=float,
            )
            rebuilt_snapshots.append(snapshot + (target_anchor - preview_anchor))
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
    anchor_xy: tuple[float, float] | None = None,
    source_rotation_deg: float = 0.0,
) -> None:
    """Write source and robot command paths to disk for offline trajectory inspection."""
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
                f"# command_count={len(pivot_path)}\n"
                f"# source_xyz_len_mm={_path_length_mm(source_path):.6f}\n"
                f"# command_xyz_len_mm={_path_length_mm(pivot_path):.6f}\n"
            )
            if pivot_pose:
                pose_values = ", ".join(f"{float(value):.6f}" for value in pivot_pose)
                handle.write(f"# pivot_pose=[{pose_values}]\n")
            if anchor_xy is not None:
                handle.write(f"# tool_anchor_xy=[{float(anchor_xy[0]):.6f}, {float(anchor_xy[1]):.6f}]\n")
            if abs(float(source_rotation_deg or 0.0)) > 1e-9:
                handle.write(f"# source_rotation_deg={float(source_rotation_deg):.6f}\n")

            for section_name, path in (
                ("ORIGINAL_PLATFORM_PATH", source_path),
                ("ROBOT_COMMAND_PATH", pivot_path),
            ):
                handle.write(f"\n[{section_name}]\n")
                handle.write(f"count={len(path)}\n")
                for index, point in enumerate(path):
                    coords = ", ".join(f"{float(value):.6f}" for value in point)
                    handle.write(f"  {index:04d}: [{coords}]\n")
            if diagnostics:
                handle.write("\n[ROTATION_DIAGNOSTICS]\n")
                for entry in diagnostics:
                    extra_fields = []
                    for key in (
                        "command_rz",
                        "command_rotation_delta",
                    ):
                        if key in entry:
                            extra_fields.append(f"{key}={float(entry.get(key, 0.0)):.6f}")
                    extra_suffix = ", " + ", ".join(extra_fields) if extra_fields else ""
                    handle.write(
                        "  {index:04d}: segment_length={segment_length:.6f}, "
                        "segment_heading={segment_heading:.6f}, "
                        "rotation_delta_raw={rotation_delta_raw:.6f}, "
                        "rotation_delta_applied={rotation_delta_applied:.6f}, "
                        "current_rz={current_rz:.6f}, "
                        "contact_error_mm={contact_error_mm:.6f}, "
                        "contact_correction_mm={contact_correction_mm:.6f}{extra_suffix}\n".format(
                            index=int(entry.get("index", 0)),
                            segment_length=float(entry.get("segment_length", 0.0)),
                            segment_heading=float(entry.get("segment_heading", 0.0)),
                            rotation_delta_raw=float(entry.get("rotation_delta_raw", 0.0)),
                            rotation_delta_applied=float(entry.get("rotation_delta_applied", 0.0)),
                            current_rz=float(entry.get("current_rz", 0.0)),
                            contact_error_mm=float(entry.get("contact_error_mm", 0.0)),
                            contact_correction_mm=float(entry.get("contact_correction_mm", 0.0)),
                            extra_suffix=extra_suffix,
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
    anchor_xy: tuple[float, float] | None = None,
    source_rotation_deg: float = 0.0,
    pattern_type: str,
    stage: str,
) -> None:
    """Write a compact visual debug plot for the source and robot command trajectories."""
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
                anchor_xy=anchor_xy,
                source_rotation_deg=source_rotation_deg,
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

        fig.suptitle(f"Pivot Command Trajectory Debug: {pattern_type} [{pivot_config.motion_plane}]", fontsize=12)

        arrow_step = max(1, len(source_xy) // 12)
        ax_source.plot(source_xy[:, 0], source_xy[:, 1], color="#1f77b4", linewidth=1.5)
        ax_source.scatter(source_xy[0, 0], source_xy[0, 1], color="green", s=40, label="start")
        ax_source.scatter(source_xy[-1, 0], source_xy[-1, 1], color="red", s=40, label="end")
        if anchor_xy is not None:
            anchor_x = float(anchor_xy[0])
            anchor_y = float(anchor_xy[1])
            ax_source.scatter(
                anchor_x,
                anchor_y,
                color="#ff7f0e",
                s=65,
                marker="x",
                linewidths=2.0,
                label="tool_anchor_xy",
                zorder=6,
            )
            ax_source.annotate(
                "tool anchor",
                xy=(anchor_x, anchor_y),
                xytext=(6, 6),
                textcoords="offset points",
                color="#ff7f0e",
                fontsize=8,
            )
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
        ax_projected.set_title("Robot Command Path")
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

        anchor_text = ""
        if anchor_xy is not None:
            anchor_text = f"   tool_anchor_xy=({float(anchor_xy[0]):.3f}, {float(anchor_xy[1]):.3f})"

        fig.text(
            0.5,
            0.01,
            (
                f"source_xyz_len={_path_length_mm(source_path):.1f} mm   "
                f"command_xyz_len={_path_length_mm(pivot_path):.1f} mm   "
                f"translation_axis={pivot_config.translation_axis}   "
                f"plane={pivot_config.motion_plane}"
                f"{anchor_text}"
            ),
            ha="center",
            fontsize=9,
        )
        fig.savefig(filepath, dpi=180)
        plt.close(fig)
        _logger.info("[PIVOT] Wrote pivot trajectory debug plot to %s", filepath)
    except Exception:
        _logger.debug("[PIVOT] Failed to write pivot trajectory debug plot", exc_info=True)

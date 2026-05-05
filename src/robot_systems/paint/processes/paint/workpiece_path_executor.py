from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Callable, Optional

import numpy as np

from src.engine.geometry.planar import rotate_xy_about, unwrap_degrees
from src.applications.workpiece_editor.service.i_workpiece_path_executor import (
    IWorkpiecePathExecutor,
    WorkpieceProcessAction,
)
from src.engine.robot.path_preparation import IWorkpiecePathPreparationService
from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import (
    PaintSimulationConfig,
    _PAINT_MOTION_PLANE_SPECS,
    _PAINT_SIDE_SIGNS,
    _PAINT_TRANSLATION_DIRECTION_SIGNS,
    _PICKUP_APPROACH_OFFSET_MM,
    _PICKUP_CONTACT_OFFSET_MM,
    _PICKUP_DEFAULT_ACC_PERCENT,
    _PICKUP_DEFAULT_VEL_PERCENT,
)
from src.robot_systems.paint.processes.paint.pivot_projection import (
    project_paint_motion_geometry,
    rebase_projected_paint_path_to_zero_start_rz,
)

_logger = logging.getLogger(__name__)


def _elapsed_s(start: float) -> float:
    return perf_counter() - float(start)


def _blend_pose(start_pose: list[float], end_pose: list[float], ratio: float) -> list[float]:
    """Linearly interpolate a 6D pose, unwrapping orientation against the start pose."""
    ratio = max(0.0, min(1.0, float(ratio)))
    pose: list[float] = []
    for index in range(6):
        start_value = float(start_pose[index])
        end_value = float(end_pose[index])
        if index >= 3:
            end_value = float(np.unwrap(np.radians([start_value, end_value]))[-1] * 180.0 / np.pi)
        pose.append(start_value + (end_value - start_value) * ratio)
    return pose


def _path_length_mm(path: list[list[float]]) -> float:
    """Return the cumulative Cartesian XYZ path length."""
    if len(path) < 2:
        return 0.0
    total = 0.0
    for start_pose, end_pose in zip(path, path[1:]):
        total += float(np.linalg.norm(np.asarray(end_pose[:3], dtype=float) - np.asarray(start_pose[:3], dtype=float)))
    return total


def _axis_label_from_index(index: int) -> str:
    return {0: "X", 1: "Y", 2: "Z"}.get(int(index), f"Axis {index}")


@dataclass(frozen=True)
class PickupToPivotPlan:
    """Concrete pickup and staging poses derived from one prepared execution plan."""
    pickup_approach_pose: list[float]
    pickup_pose: list[float]
    lift_pose: list[float]
    align_pose: list[float]
    stage_transition_poses: list[list[float]]
    staged_pose: list[float]
    change_plane_pose: list[float]

def _normalize_pivot_config(
    *,
    motion_plane: str = "xy_z_rz",
    translation_axis: str = "x",
    pivot_side: str = "negative",
    translation_direction: str = "forward",
    apply_camera_to_tcp_for_pickup: bool = False,
    camera_to_tcp_x_offset: float = 0.0,
    camera_to_tcp_y_offset: float = 0.0,
) -> PaintSimulationConfig:
    """Normalize user-facing pivot settings into a validated simulation config."""
    plane_key = str(motion_plane or "xy_z_rz").strip().lower()
    axis_key = str(translation_axis or "x").strip().lower()
    side_key = str(pivot_side or "negative").strip().lower()
    direction_key = str(translation_direction or "forward").strip().lower()
    plane_spec = _PAINT_MOTION_PLANE_SPECS.get(plane_key, _PAINT_MOTION_PLANE_SPECS["xy_z_rz"])
    valid_axes = tuple(plane_spec["axis_offsets_deg"].keys())
    return PaintSimulationConfig(
        motion_plane=plane_key if plane_key in _PAINT_MOTION_PLANE_SPECS else "xy_z_rz",
        translation_axis=axis_key if axis_key in valid_axes else valid_axes[0],
        paint_side=side_key if side_key in _PAINT_SIDE_SIGNS else "negative",
        translation_direction=(
            direction_key if direction_key in _PAINT_TRANSLATION_DIRECTION_SIGNS else "forward"
        ),
        apply_camera_to_tcp_for_pickup=bool(apply_camera_to_tcp_for_pickup),
        camera_to_tcp_x_offset=float(camera_to_tcp_x_offset),
        camera_to_tcp_y_offset=float(camera_to_tcp_y_offset),
    )


class PaintWorkpiecePathExecutor(IWorkpiecePathExecutor):
    """Execute prepared paint paths, including pickup, staging, and pivot painting."""
    def __init__(
        self,
        robot_service,
        path_preparation_service: Optional[IWorkpiecePathPreparationService] = None,
        base_position_provider: Optional[Callable[[], Optional[list[float]]]] = None,
        pickup_base_position_provider: Optional[Callable[[], Optional[list[float]]]] = None,
        post_execute_callback: Optional[Callable[[], bool]] = None,
        robot_config_provider: Optional[Callable[[], object]] = None,
        vacuum_pump=None,
        enable_vacuum_pump: bool = True,
        pickup_tool: int = 0,
        pickup_user: int = 0,
        pickup_z_mm: float | None = None,
        debug_dump_dir: str | None = None,
        pivot_motion_plane: str = "xy_z_rz",
        pivot_translation_axis: str = "x",
        pivot_side: str = "negative",
        pivot_translation_direction: str = "forward",
        flip_xz_ry_execution_rotation_direction: bool = False,
        enable_xz_ry_preflight: bool = True,
        xz_ry_preflight_max_checks: int = 8,
        apply_camera_to_tcp_for_pickup: bool = False,
        camera_to_tcp_x_offset: float = 0.0,
        camera_to_tcp_y_offset: float = 0.0,
    ) -> None:
        """Store robot dependencies and initialize the pivot/pickup execution configuration."""
        self._robot_service = robot_service
        self._path_preparation_service = path_preparation_service
        self._base_position_provider = base_position_provider
        self._pickup_base_position_provider = pickup_base_position_provider or base_position_provider
        self._post_execute_callback = post_execute_callback
        self._robot_config_provider = robot_config_provider
        self._vacuum_pump = vacuum_pump
        self._enable_vacuum_pump = bool(enable_vacuum_pump)
        self._pickup_tool = int(pickup_tool)
        self._pickup_user = int(pickup_user)
        self._pickup_z_mm = None if pickup_z_mm is None else float(pickup_z_mm)
        self._pickup_safety_z_min_mm = 100.0
        self._debug_dump_dir = debug_dump_dir
        self._last_execution_plan: WorkpieceExecutionPlan | None = None
        self._last_pickup_plan: PickupToPivotPlan | None = None
        self._pending_stage_pose: list[float] | None = None
        self._flip_xz_ry_execution_rotation_direction = bool(flip_xz_ry_execution_rotation_direction)
        self._enable_xz_ry_preflight = bool(enable_xz_ry_preflight)
        self._xz_ry_preflight_max_checks = max(1, int(xz_ry_preflight_max_checks))
        self._pivot_config = _normalize_pivot_config(
            motion_plane=pivot_motion_plane,
            translation_axis=pivot_translation_axis,
            pivot_side=pivot_side,
            translation_direction=pivot_translation_direction,
            apply_camera_to_tcp_for_pickup=apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=camera_to_tcp_y_offset,
        )
        self._pickup_pivot_config = _normalize_pivot_config(
            motion_plane="xy_z_rz",
            translation_axis=pivot_translation_axis,
            pivot_side=pivot_side,
            translation_direction=pivot_translation_direction,
            apply_camera_to_tcp_for_pickup=apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=camera_to_tcp_y_offset,
        )
        self._last_process_start_rz: float | None = None
        self._last_process_end_pose: list[float] | None = None

    def _uses_xz_ry_pivot_mode(self) -> bool:
        """Return True only for the pivot mode that shows the reachability issue."""
        return str(self._pivot_config.motion_plane).strip().lower() == "xz_y_ry"

    def _validate_xz_ry_pivot_path(self, pivot_path: list[list[float]]) -> tuple[bool, str]:
        """Preflight sampled pivot-path segments for xz/ry mode only.

        This is intentionally narrow so the established xy/rz flow is unchanged.
        """
        if not self._uses_xz_ry_pivot_mode():
            return True, ""
        if not self._enable_xz_ry_preflight:
            _logger.info("[PIVOT_PATH] xz/ry preflight skipped: disabled by configuration")
            return True, ""
        if self._robot_service is None or len(pivot_path) < 2:
            return True, ""

        # Sample a handful of segments across the full path so we can fail early
        # with a concrete offending segment instead of waiting for execute_path().
        max_checks = self._xz_ry_preflight_max_checks
        last_index = len(pivot_path) - 1
        sampled_indices = sorted(
            {
                0,
                last_index,
                *(
                    int(round(i * last_index / max_checks))
                    for i in range(1, max_checks)
                ),
            }
        )

        current_start = list(pivot_path[sampled_indices[0]])
        for waypoint_index in sampled_indices[1:]:
            target_pose = list(pivot_path[waypoint_index])
            result = self._robot_service.validate_pose(
                current_start,
                target_pose,
                tool=self._pickup_tool,
                user=self._pickup_user,
            )
            if result.get("supported") is False:
                _logger.info(
                    "[PIVOT_PATH] xz/ry preflight skipped: reachability validation not supported"
                )
                return True, ""
            if not bool(result.get("reachable")):
                reason = str(result.get("reason") or result.get("error") or "unreachable")
                _logger.warning(
                    "[PIVOT_PATH] xz/ry preflight failed at sampled waypoint %d/%d: "
                    "start=%s target=%s reason=%s result=%s",
                    waypoint_index,
                    len(pivot_path) - 1,
                    [round(float(v), 3) for v in current_start[:6]],
                    [round(float(v), 3) for v in target_pose[:6]],
                    reason,
                    result,
                )
                return False, (
                    "Pickup succeeded, but xz/ry pivot path is unreachable before execution "
                    f"(sampled waypoint {waypoint_index + 1}/{len(pivot_path)}, reason={reason})"
                )
            current_start = target_pose

        return True, ""

    def prepare_workpiece_preview(self, workpiece: dict) -> WorkpieceExecutionPlan:
        """Build and cache the execution plan for a paint workpiece."""
        if self._path_preparation_service is None:
            raise RuntimeError("Path preparation service is not available")
        self._last_execution_plan = self._path_preparation_service.build_execution_plan(workpiece)
        return self._last_execution_plan

    def get_last_execution_plan(self) -> WorkpieceExecutionPlan | None:
        """Return the last paint preview plan prepared by this executor."""
        return self._last_execution_plan

    def _refresh_runtime_config(self) -> None:
        """Refresh robot-dependent pickup settings from the latest robot configuration."""
        if self._robot_config_provider is None:
            return
        try:
            robot_config = self._robot_config_provider()
        except Exception:
            _logger.debug("[PICKUP] Failed to refresh robot config", exc_info=True)
            return
        if robot_config is None:
            return
        self._pickup_tool = int(getattr(robot_config, "robot_tool", self._pickup_tool))
        self._pickup_user = int(getattr(robot_config, "robot_user", self._pickup_user))
        try:
            self._pickup_safety_z_min_mm = float(getattr(getattr(robot_config, "safety_limits", None), "z_min", self._pickup_safety_z_min_mm))
        except Exception:
            pass
        self._pivot_config = _normalize_pivot_config(
            motion_plane=self._pivot_config.motion_plane,
            translation_axis=self._pivot_config.translation_axis,
            pivot_side=self._pivot_config.paint_side,
            translation_direction=self._pivot_config.translation_direction,
            apply_camera_to_tcp_for_pickup=self._pivot_config.apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=float(getattr(robot_config, "camera_to_tcp_x_offset", self._pivot_config.camera_to_tcp_x_offset)),
            camera_to_tcp_y_offset=float(getattr(robot_config, "camera_to_tcp_y_offset", self._pivot_config.camera_to_tcp_y_offset)),
        )
        self._pickup_pivot_config = _normalize_pivot_config(
            motion_plane="xy_z_rz",
            translation_axis=self._pickup_pivot_config.translation_axis,
            pivot_side=self._pickup_pivot_config.paint_side,
            translation_direction=self._pickup_pivot_config.translation_direction,
            apply_camera_to_tcp_for_pickup=self._pickup_pivot_config.apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=float(getattr(robot_config, "camera_to_tcp_x_offset", self._pickup_pivot_config.camera_to_tcp_x_offset)),
            camera_to_tcp_y_offset=float(getattr(robot_config, "camera_to_tcp_y_offset", self._pickup_pivot_config.camera_to_tcp_y_offset)),
        )

    def _write_pivot_debug_dump(
        self,
        *,
        source_path: list[list[float]],
        pivot_path: list[list[float]],
        diagnostics: list[dict[str, float | int]] | None,
        pivot_pose: list[float] | None,
        pattern_type: str,
        stage: str,
    ) -> None:
        """Write source and projected pivot paths to disk for offline trajectory inspection."""
        if not self._debug_dump_dir:
            return

        try:
            os.makedirs(self._debug_dump_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_pattern = str(pattern_type or "path").strip().lower().replace(" ", "_")
            safe_stage = str(stage or "run").strip().lower().replace(" ", "_")
            safe_plane = str(self._pivot_config.motion_plane or "unknown").strip().lower()
            filepath = os.path.join(
                self._debug_dump_dir,
                f"pivot_trajectory_{safe_stage}_{safe_pattern}_{safe_plane}_{timestamp}.txt",
            )
            with open(filepath, "w", encoding="utf-8") as handle:
                handle.write(
                    f"# Pivot trajectory dump\n"
                    f"# timestamp={timestamp}\n"
                    f"# pattern_type={pattern_type}\n"
                    f"# stage={stage}\n"
                    f"# motion_plane={self._pivot_config.motion_plane}\n"
                    f"# translation_axis={self._pivot_config.translation_axis}\n"
                    f"# paint_side={self._pivot_config.paint_side}\n"
                    f"# translation_direction={self._pivot_config.translation_direction}\n"
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

    def _write_pivot_debug_plot(
        self,
        *,
        source_path: list[list[float]],
        pivot_path: list[list[float]],
        snapshots: list[np.ndarray] | None,
        diagnostics: list[dict[str, float | int]] | None,
        pivot_pose: list[float] | None,
        pattern_type: str,
        stage: str,
    ) -> None:
        """Write a compact visual debug plot for the source and projected pivot trajectories."""
        if not self._debug_dump_dir or not source_path or not pivot_path:
            return

        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            os.makedirs(self._debug_dump_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_pattern = str(pattern_type or "path").strip().lower().replace(" ", "_")
            safe_stage = str(stage or "run").strip().lower().replace(" ", "_")
            safe_plane = str(self._pivot_config.motion_plane or "unknown").strip().lower()
            filepath = os.path.join(
                self._debug_dump_dir,
                f"pivot_trajectory_{safe_stage}_{safe_pattern}_{safe_plane}_{timestamp}.png",
            )

            planar_i, planar_j = self._pivot_config.planar_coordinate_indices
            source_i, source_j = self._pivot_config.source_planar_coordinate_indices
            rotation_index = self._pivot_config.rotation_index

            source_xy = np.asarray([[float(p[source_i]), float(p[source_j])] for p in source_path], dtype=float)
            projected_xy = np.asarray([[float(p[planar_i]), float(p[planar_j])] for p in pivot_path], dtype=float)
            projected_rot = np.asarray(
                [float(p[rotation_index]) if len(p) > rotation_index else 0.0 for p in pivot_path],
                dtype=float,
            )
            snapshot_list = [
                np.asarray(snapshot, dtype=float)
                for snapshot in self._build_executed_snapshot_series(
                    source_path=source_path,
                    executed_path=pivot_path,
                    pivot_pose=pivot_pose,
                ) or (snapshots or [])
                if len(snapshot) >= 1
            ]
            waypoint_idx = np.arange(len(pivot_path), dtype=float)
            rotation_delta = np.asarray(
                [
                    float(entry.get("rotation_delta_applied", 0.0))
                    for entry in (diagnostics or [])
                ],
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
                snapshot_cols = min(3, max(1, len(sample_indices)))
                snapshot_rows = int(np.ceil(len(sample_indices) / snapshot_cols))
                fig = plt.figure(
                    figsize=(18, 6 + (3.2 * snapshot_rows)),
                    constrained_layout=True,
                )
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

            fig.suptitle(
                f"Pivot Trajectory Debug: {pattern_type} [{self._pivot_config.motion_plane}]",
                fontsize=12,
            )

            ax_source.plot(source_xy[:, 0], source_xy[:, 1], color="#1f77b4", linewidth=1.5)
            ax_source.scatter(source_xy[0, 0], source_xy[0, 1], color="green", s=40, label="start")
            ax_source.scatter(source_xy[-1, 0], source_xy[-1, 1], color="red", s=40, label="end")
            arrow_step = max(1, len(source_xy) // 12)
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

            scatter = ax_projected.scatter(
                projected_xy[:, 0],
                projected_xy[:, 1],
                c=waypoint_idx,
                cmap="viridis",
                s=18,
            )
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
                ax_projected.text(
                    projected_xy[0, 0],
                    projected_xy[0, 1],
                    " contact",
                    color="#d62728",
                    fontsize=8,
                )
                ax_projected.text(
                    projected_xy[1, 0],
                    projected_xy[1, 1],
                    " first move",
                    color="#d62728",
                    fontsize=8,
                )
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
                    color = snapshot_cmap(
                        0.0 if len(sample_indices) == 1 else draw_order / (len(sample_indices) - 1)
                    )
                    is_contact = int(sample_index) == 0
                    is_first_move = int(sample_index) == 1
                    line_width = 2.6 if (is_contact or is_first_move) else 1.2
                    line_style = "-" if is_contact else ("--" if is_first_move else "-")
                    ax_snapshot = snapshot_axes[draw_order]
                    ax_snapshot.plot(
                        snapshot[:, 0],
                        snapshot[:, 1],
                        color=color,
                        linewidth=line_width,
                        linestyle=line_style,
                        alpha=0.95,
                    )
                    ax_snapshot.scatter(
                        snapshot[0, 0],
                        snapshot[0, 1],
                        color=color,
                        s=42 if (is_contact or is_first_move) else 18,
                        alpha=0.95,
                    )
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
                        ax_snapshot.scatter(
                            tcp_x,
                            tcp_y,
                            color="#d62728",
                            s=28,
                            marker="o",
                            label="executed tcp",
                            zorder=5,
                        )
                    if pivot_pose is not None and len(pivot_pose) > max(planar_i, planar_j):
                        pivot_xy = np.asarray(
                            [float(pivot_pose[planar_i]), float(pivot_pose[planar_j])],
                            dtype=float,
                        )
                        nearest_index = int(np.argmin(np.linalg.norm(snapshot - pivot_xy, axis=1)))
                        nearest_point = snapshot[nearest_index]
                        ax_snapshot.scatter(
                            float(nearest_point[0]),
                            float(nearest_point[1]),
                            color="#ff7f0e",
                            s=24,
                            marker="s",
                            label="nearest to pivot",
                            zorder=5,
                        )
                    label = f"Step {int(sample_index)}"
                    if is_contact:
                        label = "Step 0 - contact"
                    elif is_first_move:
                        label = "Step 1 - first move"
                    ax_snapshot.set_title(label)
                    if pivot_pose is not None and len(pivot_pose) > max(planar_i, planar_j):
                        ax_snapshot.scatter(
                            float(pivot_pose[planar_i]),
                            float(pivot_pose[planar_j]),
                            color="orange",
                            s=55,
                            marker="x",
                            label="pivot",
                        )
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
                ax_rotation.bar(
                    waypoint_idx,
                    rotation_delta[: len(waypoint_idx)],
                    color="#9467bd",
                    alpha=0.35,
                    width=0.8,
                    label="rotation delta",
                )
                ax_rotation.axhline(0.0, color="#666666", linewidth=0.8, alpha=0.6)
                ax_rotation.set_title("Rotation Progression")
                ax_rotation.set_xlabel("Waypoint")
                ax_rotation.set_ylabel(
                    "RY (deg)" if rotation_index == 4 else "RZ (deg)"
                )
                ax_rotation.grid(True, alpha=0.25)
                ax_rotation.legend(loc="best")

            fig.text(
                0.5,
                0.01,
                (
                    f"source_xyz_len={_path_length_mm(source_path):.1f} mm   "
                    f"projected_xyz_len={_path_length_mm(pivot_path):.1f} mm   "
                    f"translation_axis={self._pivot_config.translation_axis}   "
                    f"plane={self._pivot_config.motion_plane}"
                ),
                ha="center",
                fontsize=9,
            )
            fig.savefig(filepath, dpi=180)
            plt.close(fig)
            _logger.info("[PIVOT] Wrote pivot trajectory debug plot to %s", filepath)
        except Exception:
            _logger.debug("[PIVOT] Failed to write pivot trajectory debug plot", exc_info=True)

    def _build_executed_snapshot_series(
        self,
        *,
        source_path: list[list[float]],
        executed_path: list[list[float]],
        pivot_pose: list[float] | None,
    ) -> list[np.ndarray]:
        """Rebuild contour snapshots from the final executed pose sequence."""
        if not source_path or not executed_path or pivot_pose is None or len(pivot_pose) < 3:
            return []
        try:
            preview_path, preview_snapshots, _ = project_paint_motion_geometry(
                source_path,
                pivot_pose,
                self._pivot_config,
            )
            if not preview_path or not preview_snapshots:
                return []

            planar_i, planar_j = self._pivot_config.planar_coordinate_indices
            rotation_index = self._pivot_config.rotation_index
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

    def get_supported_execution_modes(self) -> tuple[str, ...]:
        """Report the execution modes supported by the paint executor."""
        return ("pivot_path",)

    def get_process_actions(self) -> tuple[WorkpieceProcessAction, ...]:
        """Expose the paint process as one editor-facing action."""
        return (
            WorkpieceProcessAction(
                action_id="paint_process",
                label="Approve Paint Process",
                requires_projected_path_plot=True,
            ),
        )

    def execute_process_action(
        self,
        execution_plan: WorkpieceExecutionPlan,
        action_id: str,
    ) -> tuple[bool, str]:
        """Execute the requested paint process action."""
        action_id = str(action_id or "").strip().lower()
        if action_id != "paint_process":
            return False, f"Unsupported paint process action: {action_id}"
        return self.execute_pickup_and_paint(execution_plan)

    def supports_pickup_to_pivot(self) -> bool:
        """Report that this executor supports pickup and staging before paint execution."""
        return True

    def _resolve_base_position(self) -> Optional[list[float]]:
        """Resolve the configured pivot/base pose used to project paint motion."""
        provider = self._base_position_provider
        if provider is None:
            return None
        try:
            position = provider()
        except Exception:
            _logger.debug("PaintWorkpiecePathExecutor: base position provider failed", exc_info=True)
            return None
        if not position or len(position) < 3:
            return None
        try:
            return [float(position[i]) for i in range(6 if len(position) >= 6 else len(position))]
        except (TypeError, ValueError):
            return None

    def _resolve_pickup_base_position(self) -> Optional[list[float]]:
        """Resolve the pickup/staging base pose used for XY/RZ pickup alignment."""
        provider = self._pickup_base_position_provider
        if provider is None:
            return None
        try:
            position = provider()
        except Exception:
            _logger.debug("PaintWorkpiecePathExecutor: pickup base position provider failed", exc_info=True)
            return None
        if not position or len(position) < 3:
            return None
        try:
            return [float(position[i]) for i in range(6 if len(position) >= 6 else len(position))]
        except (TypeError, ValueError):
            return None

    def get_pivot_preview_paths(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[list[list[list[float]]], list[float] | None]:
        """Project preview center paths for each prepared execution job around the pivot pose."""
        pivot_pose = self._resolve_base_position()
        if pivot_pose is None or len(pivot_pose) < 3:
            return [], pivot_pose
        paths = []
        for job in execution_plan.execution_jobs:
            source_path = job.get("execution_path") or job.get("path") or []
            if not source_path:
                continue
            center_path, _, diagnostics = project_paint_motion_geometry(
                source_path,
                pivot_pose,
                self._pivot_config,
            )
            # self._write_pivot_debug_dump(
            #     source_path=source_path,
            #     pivot_path=center_path,
            #     diagnostics=diagnostics,
            #     pivot_pose=list(pivot_pose),
            #     pattern_type=str(job.get("pattern_type", "Path")),
            #     stage="preview",
            # )
            paths.append(center_path)
        return paths, list(pivot_pose)

    def get_pivot_motion_preview(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[list[list[np.ndarray]], list[float] | None]:
        """Return per-step projected shape snapshots for pivot motion preview/plotting."""
        pivot_pose = self._resolve_base_position()
        if pivot_pose is None or len(pivot_pose) < 3:
            return [], pivot_pose
        motion = []
        for job in execution_plan.execution_jobs:
            source_path = job.get("execution_path") or job.get("path") or []
            if not source_path:
                continue
            _, snapshots, _ = project_paint_motion_geometry(
                source_path,
                pivot_pose,
                self._pivot_config,
            )
            motion.append(snapshots)
        return motion, list(pivot_pose)


    def _build_pivot_execution_path(
        self,
        spline: list[list[float]],
        *,
        align_start_to_zero_rz: bool = False,
    ) -> list[list[float]] | None:
        """Project one prepared spline into the real pivot execution trajectory."""
        started = perf_counter()
        pivot_pose = self._resolve_base_position()
        if pivot_pose is None or len(pivot_pose) < 3:
            _logger.info("[TIMING] pivot_path_build status=missing_pivot elapsed_s=%.3f", _elapsed_s(started))
            return None
        pivot_path, _, _ = project_paint_motion_geometry(
            spline,
            pivot_pose,
            self._pivot_config,
        )
        _logger.debug("Simulated pivot path has %d points", len(pivot_path))
        if align_start_to_zero_rz:
            pivot_path = rebase_projected_paint_path_to_zero_start_rz(
                pivot_path,
                self._pivot_config,
            )
        _logger.info(
            "[TIMING] pivot_path_build input_pts=%d output_pts=%d zero_start_rz=%s elapsed_s=%.3f",
            len(spline),
            len(pivot_path) if pivot_path else 0,
            bool(align_start_to_zero_rz),
            _elapsed_s(started),
        )
        return pivot_path

    def execute_preview_paths(
        self,
        execution_plan: WorkpieceExecutionPlan,
        mode: str = "continuous",
    ) -> tuple[bool, str]:
        """Execute a prepared plan by projecting each path into pivot motion and sending it to the robot."""
        jobs = execution_plan.execution_jobs
        if not jobs:
            return False, "No prepared process paths available to execute"
        if self._robot_service is None:
            return False, "Robot service is not available"

        mode = str(mode or "continuous").strip().lower()
        if mode != "pivot_path":
            return False, f"Unsupported paint execution mode: {mode}"

        total_waypoints = 0
        for job in jobs:
            spline = job.get("execution_path") or job.get("path") or []
            _logger.debug(f"Execution path before build_pivot_execution_path: {len(spline)}")
            vel = float(job.get("vel", 60.0))
            acc = float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))

            if not spline:
                continue

            pivot_pose = self._resolve_base_position()
            if pivot_pose is None or len(pivot_pose) < 3:
                return False, "Pivot-path execution requires a valid base/pivot position"
            pivot_path, _, diagnostics = project_paint_motion_geometry(
                spline,
                pivot_pose,
                self._pivot_config,
            )
            if not pivot_path:
                return False, "Pivot-path execution requires a valid base/pivot position"
            _logger.debug(f"Pivot path after build_pivot_execution_path: {len(pivot_path)}")

            # self._write_pivot_debug_dump(
            #     source_path=spline,
            #     pivot_path=pivot_path,
            #     diagnostics=diagnostics,
            #     pivot_pose=pivot_pose,
            #     pattern_type=pattern_type,
            #     stage="execute",
            # )
            result = self._robot_service.execute_trajectory(
                pivot_path,
                vel=vel,
                acc=acc,
                blocking=True,
                orientation_mode="per_waypoint",
            )
            if result not in (0, True, None):
                return False, f"{pattern_type} pivot-path execution failed with code {result}"
            total_waypoints += len(spline)
            _logger.info(
                "[EXECUTE] [RUN PROCESS] Sent %d waypoints to robot in %s mode (vel=%.0f acc=%.0f)",
                len(spline), mode, vel, acc,
            )

        if self._post_execute_callback is not None:
            if not self._robot_service.unwind_joint6(
                blocking=True,
                queue_if_busy=True,
                vel=100.0,
                acc=100.0,
            ):
                return False, "Execution finished, but explicit unwind failed"
            _logger.info("[EXECUTE] Explicit Joint_6 unwind completed")
            try:
                moved = bool(self._post_execute_callback())
            except Exception:
                _logger.exception("[EXECUTE] Post-execute callback failed")
                return False, "Execution finished, but return-to-calibration failed"
            if not moved:
                return False, "Execution finished, but return-to-calibration failed"
            _logger.info("[EXECUTE] Returned to post-execution position")

        return True, (
            f"Executed {len(jobs)} path(s), "
            f"{total_waypoints} waypoints in {mode} mode"
        )

    def _build_pickup_and_stage_poses(
            self,
            execution_plan: WorkpieceExecutionPlan,
    ) -> PickupToPivotPlan | None:
        """Build XY/RZ pickup poses and the first staged pose for the active paint process plane."""
        jobs = execution_plan.execution_jobs
        self._refresh_runtime_config()
        if not jobs:
            return None

        pickup_pivot_pose = self._resolve_pickup_base_position()
        paint_pivot_pose = self._resolve_base_position()
        if pickup_pivot_pose is None or len(pickup_pivot_pose) < 3:
            return None
        if paint_pivot_pose is None or len(paint_pivot_pose) < 3:
            return None

        source_path = jobs[0].get("execution_path") or jobs[0].get("path") or []
        if not source_path:
            return None

        projected_pivot_path, _, _ = project_paint_motion_geometry(
            source_path,
            paint_pivot_pose,
            self._pivot_config,
        )
        if not projected_pivot_path:
            return None

        first_pivot_pose = list(projected_pivot_path[0])
        pickup_target_point_name = str(
            jobs[0].get("pickup_target_point_name", "") or ""
        ).strip().lower()
        workpiece_height_mm = float(jobs[0].get("workpiece_height_mm", 0.0) or 0.0)
        pickup_xy = jobs[0].get("pickup_xy")
        pickup_centroid_x = float(pickup_xy[0])
        pickup_centroid_y = float(pickup_xy[1])
        pickup_rx = float(pickup_pivot_pose[3]) if len(pickup_pivot_pose) >= 4 else 180.0
        pickup_ry = float(pickup_pivot_pose[4]) if len(pickup_pivot_pose) >= 5 else 0.0

        pickup_z = self._pickup_z_mm
        if pickup_z is None:
            pickup_z = self._pickup_safety_z_min_mm + workpiece_height_mm + _PICKUP_CONTACT_OFFSET_MM

        pickup_rz = float(jobs[0].get("pickup_rz", 0.0))
        should_apply_tcp_offset = False
        pickup_tcp_dx, pickup_tcp_dy = 0.0, 0.0
        _logger.info(
            "[PICKUP] pickup_xy=(%.3f, %.3f) pickup_rz=%.3f pickup_target=%s workpiece_height=%.3f pickup_z=%.3f safety_z_min=%.3f apply_tcp_offset=%s configured_tcp_offset=(%.3f, %.3f) rotated_tcp_offset=(%.3f, %.3f)",
            pickup_centroid_x,
            pickup_centroid_y,
            pickup_rz,
            pickup_target_point_name or "camera",
            workpiece_height_mm,
            float(pickup_z),
            self._pickup_safety_z_min_mm,
            should_apply_tcp_offset,
            self._pivot_config.camera_to_tcp_x_offset,
            self._pivot_config.camera_to_tcp_y_offset,
            pickup_tcp_dx,
            pickup_tcp_dy,
        )
        pickup_approach_z = float(pickup_z) + _PICKUP_APPROACH_OFFSET_MM
        pickup_approach_pose = [
            pickup_centroid_x - pickup_tcp_dx,
            pickup_centroid_y - pickup_tcp_dy,
            pickup_approach_z,
            pickup_rx,
            pickup_ry,
            pickup_rz,
        ]
        pickup_pose = [
            pickup_centroid_x - pickup_tcp_dx,
            pickup_centroid_y - pickup_tcp_dy,
            float(pickup_z),
            pickup_rx,
            pickup_ry,
            pickup_rz,
        ]

        align_rx = pickup_rx
        align_ry = pickup_ry
        align_rz = pickup_rz
        if self._uses_xz_ry_pivot_mode():
            target_ry = float(first_pivot_pose[4]) if len(first_pivot_pose) >= 5 else pickup_ry
            reference_ry = float(paint_pivot_pose[4]) if len(paint_pivot_pose) >= 5 else pickup_ry
            align_delta = unwrap_degrees(reference_ry, target_ry) - reference_ry
            align_rz = unwrap_degrees(pickup_rz, pickup_rz + align_delta)
        else:
            align_rz = float(first_pivot_pose[5]) if len(first_pivot_pose) >= 6 else pickup_rz

        align_pose = [
            pickup_centroid_x - pickup_tcp_dx,
            pickup_centroid_y - pickup_tcp_dy,
            pickup_approach_z,
            align_rx,
            align_ry,
            align_rz,
        ]

        change_plane_pose = [
            pickup_centroid_x - pickup_tcp_dx,
            pickup_centroid_y - pickup_tcp_dy,
            float(pickup_approach_z),
            float(paint_pivot_pose[3]) if len(paint_pivot_pose) >= 4 else pickup_rx,
            pickup_ry,
            align_rz,
        ]

        staged_pose = list(first_pivot_pose)
        stage_transition_poses: list[list[float]] = []
        return PickupToPivotPlan(
            pickup_approach_pose=pickup_approach_pose,
            pickup_pose=pickup_pose,
            lift_pose=list(pickup_approach_pose),
            change_plane_pose=change_plane_pose,
            align_pose=align_pose,
            stage_transition_poses=stage_transition_poses,
            staged_pose=staged_pose,
        )

    def _move_pickup_phase(self, label: str, pose: list[float]) -> bool:
        """Execute one pickup-related robot move with the configured pickup tool and user."""
        started = perf_counter()
        _logger.info(
            "[PICKUP] %s tool=%d user=%d pose=%s",
            label,
            self._pickup_tool,
            self._pickup_user,
            [round(v, 3) for v in pose],
        )
        ok = self._robot_service.move_ptp(
            position=pose,
            tool=self._pickup_tool,
            user=self._pickup_user,
            velocity=_PICKUP_DEFAULT_VEL_PERCENT,
            acceleration=_PICKUP_DEFAULT_ACC_PERCENT,
            wait_to_reach=True,
        )
        _logger.info("[TIMING] pickup_phase label=%s success=%s elapsed_s=%.3f", label, bool(ok), _elapsed_s(started))
        return ok

    def _turn_vacuum_on(self) -> tuple[bool, str]:
        """Enable the vacuum pump before pickup if one is configured."""
        started = perf_counter()
        if not self._enable_vacuum_pump:
            _logger.info("[TIMING] vacuum_on skipped=true reason=disabled_by_configuration elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        if self._vacuum_pump is None:
            _logger.info("[TIMING] vacuum_on skipped=true elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        _logger.info("[PICKUP] Turning vacuum pump ON before pickup")
        if self._vacuum_pump.turn_on():
            _logger.info("[TIMING] vacuum_on success=true elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        _logger.info("[TIMING] vacuum_on success=false elapsed_s=%.3f", _elapsed_s(started))
        return False, "Pickup approach succeeded, but vacuum pump ON failed"

    def _turn_vacuum_off(self) -> tuple[bool, str]:
        """Disable the vacuum pump after staging if one is configured."""
        started = perf_counter()
        if not self._enable_vacuum_pump:
            _logger.info("[TIMING] vacuum_off skipped=true reason=disabled_by_configuration elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        if self._vacuum_pump is None:
            _logger.info("[TIMING] vacuum_off skipped=true elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        _logger.info("[PICKUP] Turning vacuum pump OFF after staged pivot move")
        if self._vacuum_pump.turn_off():
            _logger.info("[TIMING] vacuum_off success=true elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        _logger.info("[TIMING] vacuum_off success=false elapsed_s=%.3f", _elapsed_s(started))
        return False, "Pickup succeeded, but vacuum pump OFF failed after pivot stage"

    def _run_pre_release_dropoff(self) -> tuple[bool, str]:
        """Return to the saved pickup-align area before releasing the workpiece."""
        started = perf_counter()
        plan = self._last_pickup_plan
        if plan is None:
            _logger.info("[TIMING] pre_release_dropoff skipped=true reason=no_pickup_plan elapsed_s=%.3f", _elapsed_s(started))
            return True, ""

        move_started = perf_counter()
        if not self._move_pickup_phase("Returning to align pose for release", plan.align_pose):
            _logger.info(
                "[TIMING] pre_release_dropoff success=false stage=align elapsed_s=%.3f total_elapsed_s=%.3f",
                _elapsed_s(move_started),
                _elapsed_s(started),
            )
            return False, "Pivot paint finished, but return-to-align move failed before release"

        rotate_started = perf_counter()
        if not self._move_pickup_phase("Changing back to original pickup orientation", plan.pickup_approach_pose):
            _logger.info(
                "[TIMING] pre_release_dropoff success=false stage=restore_orientation move_elapsed_s=%.3f rotate_elapsed_s=%.3f total_elapsed_s=%.3f",
                _elapsed_s(move_started),
                _elapsed_s(rotate_started),
                _elapsed_s(started),
            )
            return False, "Pivot paint finished, but original-orientation restore failed before release"

        _logger.info(
            "[TIMING] pre_release_dropoff success=true align_elapsed_s=%.3f restore_elapsed_s=%.3f total_elapsed_s=%.3f",
            _elapsed_s(move_started),
            _elapsed_s(rotate_started),
            _elapsed_s(started),
        )
        return True, ""

    def _run_post_execute_return(self, failure_message: str) -> tuple[bool, str]:
        """Run unwind and post-execution return logic after pivot painting finishes."""
        started = perf_counter()
        if self._post_execute_callback is None:
            _logger.info("[TIMING] post_execute_return skipped=true elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        unwind_started = perf_counter()
        if not self._robot_service.unwind_joint6(
            blocking=True,
            queue_if_busy=True,
            vel=100.0,
            acc=100.0,
        ):
            _logger.info("[TIMING] post_execute_return stage=unwind success=false total_elapsed_s=%.3f", _elapsed_s(started))
            return False, failure_message.format(reason="explicit unwind failed")
        try:
            return_started = perf_counter()
            moved = bool(self._post_execute_callback())
        except Exception:
            _logger.exception("[EXECUTE] Post-execute callback failed")
            _logger.info(
                "[TIMING] post_execute_return stage=return success=false unwind_elapsed_s=%.3f total_elapsed_s=%.3f",
                _elapsed_s(unwind_started),
                _elapsed_s(started),
            )
            return False, failure_message.format(reason="return-to-calibration failed")
        if not moved:
            _logger.info(
                "[TIMING] post_execute_return stage=return success=false unwind_elapsed_s=%.3f return_elapsed_s=%.3f total_elapsed_s=%.3f",
                _elapsed_s(unwind_started),
                _elapsed_s(return_started),
                _elapsed_s(started),
            )
            return False, failure_message.format(reason="return-to-calibration failed")
        _logger.info(
            "[TIMING] post_execute_return success=true unwind_elapsed_s=%.3f return_elapsed_s=%.3f total_elapsed_s=%.3f",
            _elapsed_s(unwind_started),
            _elapsed_s(return_started),
            _elapsed_s(started),
        )
        return True, ""

    def _execute_pivot_paths(self, execution_plan: WorkpieceExecutionPlan) -> tuple[bool, str, int]:
        """Execute all projected pivot paint paths in the prepared execution plan."""
        started = perf_counter()
        total_waypoints = 0
        self._refresh_runtime_config()
        self._last_process_start_rz = None
        self._last_process_end_pose = None
        for job_index, job in enumerate(execution_plan.execution_jobs, start=1):
            job_started = perf_counter()
            spline = job.get("execution_path") or job.get("path") or []
            vel = float(job.get("vel", 10.0))
            acc = float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))
            if not spline:
                continue

            pivot_path = self._build_pivot_execution_path(spline, align_start_to_zero_rz=False)
            if not pivot_path:
                _logger.info(
                    "[TIMING] pivot_job index=%d pattern=%s success=false stage=build total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    _elapsed_s(job_started),
                )
                return False, "Pickup succeeded, but pivot-path geometry could not be built", total_waypoints
            if self._uses_xz_ry_pivot_mode() and self._flip_xz_ry_execution_rotation_direction and pivot_path:
                reference_ry = float(pivot_path[0][4]) if len(pivot_path[0]) >= 5 else 0.0
                for pose in pivot_path:
                    if len(pose) >= 5:
                        pose[4] = 2.0 * reference_ry - float(pose[4])
                _logger.info(
                    "[PIVOT_PATH] Flipped xz/ry execution rotation direction around start RY=%.3f",
                    reference_ry,
                )
            if self._last_process_start_rz is None and pivot_path:
                self._last_process_start_rz = float(pivot_path[0][5]) if len(pivot_path[0]) >= 6 else 0.0

            first_pose = [round(float(value), 3) for value in pivot_path[0][:6]]
            last_pose = [round(float(value), 3) for value in pivot_path[-1][:6]]
            staged_delta_mm = 0.0
            if self._last_process_end_pose is None and pivot_path:
                staged_delta_mm = float(
                    np.linalg.norm(
                        np.asarray(pivot_path[0][:3], dtype=float)
                        - np.asarray(execution_plan.execution_jobs[0].get("execution_path", pivot_path)[0][:3], dtype=float)
                    )
                )
            _logger.info(
                "[PIVOT_PATH] job=%d first_pose=%s last_pose=%s total_xyz_len_mm=%.3f",
                job_index,
                first_pose,
                last_pose,
                _path_length_mm(pivot_path),
            )

            pivot_pose = self._resolve_base_position()
            if pivot_pose is not None and len(pivot_pose) >= 3:
                _, snapshots, diagnostics = project_paint_motion_geometry(
                    spline,
                    pivot_pose,
                    self._pivot_config,
                )
            else:
                snapshots = None
                diagnostics = None
            self._write_pivot_debug_dump(
                source_path=spline,
                pivot_path=pivot_path,
                diagnostics=diagnostics,
                pivot_pose=list(pivot_pose) if pivot_pose is not None else None,
                pattern_type=pattern_type,
                stage="execute",
            )
            self._write_pivot_debug_plot(
                source_path=spline,
                pivot_path=pivot_path,
                snapshots=snapshots,
                diagnostics=diagnostics,
                pivot_pose=list(pivot_pose) if pivot_pose is not None else None,
                pattern_type=pattern_type,
                stage="execute",
            )

            preflight_ok, preflight_message = self._validate_xz_ry_pivot_path(pivot_path)
            if not preflight_ok:
                _logger.info(
                    "[TIMING] pivot_job index=%d pattern=%s success=false stage=preflight input_pts=%d output_pts=%d total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    len(spline),
                    len(pivot_path),
                    _elapsed_s(job_started),
                )
                return False, preflight_message, total_waypoints

            execute_started = perf_counter()
            result = self._robot_service.execute_trajectory(
                pivot_path,
                vel=vel,
                acc=acc,
                blocking=True,
                orientation_mode="per_waypoint",
            )
            if result not in (0, True, None):
                _logger.info(
                    "[TIMING] pivot_job index=%d pattern=%s success=false input_pts=%d output_pts=%d execute_elapsed_s=%.3f total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    len(spline),
                    len(pivot_path),
                    _elapsed_s(execute_started),
                    _elapsed_s(job_started),
                )
                return False, f"Pickup succeeded, but {pattern_type} pivot paint failed with code {result}", total_waypoints
            total_waypoints += len(spline)
            self._last_process_end_pose = list(pivot_path[-1])
            _logger.info(
                "[TIMING] pivot_job index=%d pattern=%s success=true input_pts=%d output_pts=%d execute_elapsed_s=%.3f total_elapsed_s=%.3f",
                job_index,
                pattern_type,
                len(spline),
                len(pivot_path),
                _elapsed_s(execute_started),
                _elapsed_s(job_started),
            )
        _logger.info(
            "[TIMING] pivot_paths success=true jobs=%d total_waypoints=%d elapsed_s=%.3f",
            len(execution_plan.execution_jobs),
            total_waypoints,
            _elapsed_s(started),
        )
        return True, "", total_waypoints

    def execute_pickup_to_pivot(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[bool, str]:
        """Run the pickup-only sequence: approach, vacuum on, descend, lift, and stage at the pivot."""
        started = perf_counter()
        if self._robot_service is None:
            return False, "Robot service is not available"

        plan_started = perf_counter()
        plan = self._build_pickup_and_stage_poses(execution_plan)
        if plan is None:
            _logger.info("[TIMING] pickup_to_pivot success=false stage=build_poses total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Could not compute pickup-to-pivot poses"
        self._last_pickup_plan = plan
        _logger.info("[TIMING] pickup_to_pivot stage=build_poses elapsed_s=%.3f", _elapsed_s(plan_started))

        ok, msg = self._turn_vacuum_on()
        if not ok:
            _logger.info("[TIMING] pickup_to_pivot success=false stage=vacuum_on total_elapsed_s=%.3f", _elapsed_s(started))
            return False, msg

        if not self._move_pickup_phase("Moving to pickup approach pose", plan.pickup_approach_pose):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=approach total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup approach move failed"

        if not self._move_pickup_phase("Descending to pickup pose", plan.pickup_pose):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=descend total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup descend move failed"

        if not self._move_pickup_phase("Lifting from pickup pose", plan.lift_pose):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=lift total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup succeeded, but lift move failed"

        if not self._move_pickup_phase("Aligning rotation at pickup pose", plan.align_pose):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=align total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup succeeded, but align move failed"

        if not self._move_pickup_phase("Changing plane", plan.change_plane_pose):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=change_plane total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup succeeded, but change-plane move failed"

        for transition_index, transition_pose in enumerate(plan.stage_transition_poses, start=1):
            if not self._move_pickup_phase(
                f"Stage transition {transition_index}",
                transition_pose,
            ):
                _logger.info(
                    "[TIMING] pickup_to_pivot success=false stage=stage_transition_%d total_elapsed_s=%.3f",
                    transition_index,
                    _elapsed_s(started),
                )
                return False, f"Pickup succeeded, but stage transition {transition_index} failed"

        if not self._move_pickup_phase("Moving to first pivot contact pose", plan.staged_pose):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=staged_pose total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup succeeded, but move to first pivot contact pose failed"
        _logger.info("[TIMING] pickup_to_pivot success=true total_elapsed_s=%.3f", _elapsed_s(started))
        return True, "Pickup completed and robot is positioned at the first pivot contact pose"

    def execute_pickup_and_paint(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[bool, str]:
        """Run pickup, staging, projected pivot paint execution, and post-run return."""
        started = perf_counter()
        ok, msg = self.execute_pickup_to_pivot(execution_plan)
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=pickup total_elapsed_s=%.3f", _elapsed_s(started))
            return False, msg

        ok, msg, total_waypoints = self._execute_pivot_paths(execution_plan)
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=pivot total_elapsed_s=%.3f", _elapsed_s(started))
            return False, msg

        ok, msg = self._run_pre_release_dropoff()
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=pre_release_dropoff total_elapsed_s=%.3f", _elapsed_s(started))
            return False, msg

        ok, msg = self._turn_vacuum_off()
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=vacuum_off total_elapsed_s=%.3f", _elapsed_s(started))
            return False, msg

        ok, msg = self._run_post_execute_return(
            "Pickup and pivot paint finished, but {reason}"
        )
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=post_return total_elapsed_s=%.3f", _elapsed_s(started))
            return False, msg

        _logger.info(
            "[TIMING] pickup_and_paint success=true jobs=%d total_waypoints=%d total_elapsed_s=%.3f",
            len(execution_plan.execution_jobs),
            total_waypoints,
            _elapsed_s(started),
        )
        return True, (
            f"Pickup, alignment, and pivot paint completed "
            f"for {len(execution_plan.execution_jobs)} path(s), {total_waypoints} waypoints"
        )

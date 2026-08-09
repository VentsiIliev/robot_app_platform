from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from src.engine.geometry.planar import unwrap_degrees
from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.plan.paint_contact_motion import (
    project_paint_contact_motion_continuous,
)
from src.robot_systems.paint.timing import timed_block

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PickupTransferPlan:
    """Concrete pickup and staging poses derived from one prepared paint workpiece."""

    pickup_approach_pose: list[float]
    pickup_pose: list[float]
    lift_pose: list[float]
    align_pose: list[float]
    stage_transition_poses: list[list[float]]
    staged_pose: list[float]
    change_plane_pose: list[float]
    paint_pivot_pose: list[float]
    safe_travel_poses: list[list[float]] = field(default_factory=list)
    safe_travel_waypoints: list[dict] = field(default_factory=list)
    source_rotation_deg: float = 0.0
    projected_source_path: list[list[float]] | None = None
    projected_pivot_path: list[list[float]] | None = None
    projected_snapshots: list[np.ndarray] | None = None
    projected_diagnostics: list[dict[str, float | int]] | None = None


PickupToPivotPlan = PickupTransferPlan


class PaintPickupTransferPlanner:
    """Build the carried-workpiece transfer plan from pickup pose to paint pivot contact."""

    def __init__(self, owner) -> None:
        self._owner = owner

    def build_plan(self, prepared_workpiece: WorkpieceExecutionPlan) -> PickupTransferPlan | None:
        """Build XY/RZ pickup poses and the first staged pose for the active paint process plane."""
        from src.robot_systems.paint.processes.paint.execute.projection_preview import (
            pivot_source_path,
            projection_tool_anchor_xy,
        )
        from src.robot_systems.paint.processes.paint.execute.workpiece_path_executor import _camera_to_tcp_delta

        owner = self._owner
        jobs = prepared_workpiece.execution_jobs
        with timed_block(_logger, "pickup_plan_build", label="refresh_process_config"):
            owner._refresh_paint_process_config_snapshot()
            owner._apply_paint_process_contact_config()
        with timed_block(_logger, "pickup_plan_build", label="refresh_runtime_config"):
            owner._refresh_runtime_config()
        if not jobs:
            return None

        with timed_block(_logger, "pickup_plan_build", label="resolve_pickup_base_position"):
            pickup_pivot_pose = owner._resolve_pickup_base_position()
        _logger.debug("pickup_pivot_pose -> %s", pickup_pivot_pose)

        with timed_block(_logger, "pickup_plan_build", label="resolve_paint_base_position"):
            paint_pivot_pose = owner._resolve_base_position()
        _logger.debug("paint_pivot_pose -> %s", paint_pivot_pose)

        if pickup_pivot_pose is None or len(pickup_pivot_pose) < 3:
            return None
        if paint_pivot_pose is None or len(paint_pivot_pose) < 3:
            return None

        source_path = pivot_source_path(jobs[0], owner._contact_motion_config)
        if not source_path:
            return None

        pickup_xy = jobs[0].get("pickup_xy")
        if not pickup_xy or len(pickup_xy) < 2:
            return None

        pickup_centroid_x = float(pickup_xy[0])
        pickup_centroid_y = float(pickup_xy[1])
        anchor_xy = projection_tool_anchor_xy(jobs[0], owner._contact_motion_config)
        pivot_offset_mm = owner._resolve_pivot_offset_mm(jobs[0], prepared_workpiece)
        paint_pivot_pose = owner._apply_pivot_offset(paint_pivot_pose, pivot_offset_mm)

        if paint_pivot_pose is None or len(paint_pivot_pose) < 3:
            return None

        pickup_rz = float(jobs[0].get("pickup_rz", 0.0))
        pickup_reference_rz = float(
            jobs[0].get(
                "pickup_reference_rz",
                float(pickup_pivot_pose[5]) if len(pickup_pivot_pose) >= 6 else 0.0,
            )
        )
        align_rz = pickup_reference_rz
        source_rotation_deg = unwrap_degrees(float(pickup_rz), float(align_rz)) - float(pickup_rz)

        with timed_block(_logger, "pickup_plan_build", label="project_pivot_path"):
            projected_pivot_path, projected_snapshots, projected_diagnostics = project_paint_contact_motion_continuous(
                source_path,
                paint_pivot_pose,
                owner._contact_motion_config,
                anchor_xy=anchor_xy,
                source_rotation_deg=source_rotation_deg,
            )

        if not projected_pivot_path:
            return None

        first_pivot_pose = list(projected_pivot_path[0])
        _logger.debug("first_pivot_pose -> %s", first_pivot_pose)

        if abs(source_rotation_deg) > 1e-9:
            _logger.info(
                "[PICKUP] carried source rotation applied to pivot geometry: pickup_rz=%.3f align_rz=%.3f source_rotation_deg=%.3f first_pivot=%s",
                float(pickup_rz),
                float(align_rz),
                float(source_rotation_deg),
                [round(float(v), 3) for v in first_pivot_pose[:6]],
            )

        if anchor_xy is not None and len(source_path[0]) >= 2 and len(first_pivot_pose) >= 3:
            self._log_anchor_offset(
                source_path=source_path,
                first_pivot_pose=first_pivot_pose,
                paint_pivot_pose=paint_pivot_pose,
                anchor_xy=anchor_xy,
            )

        pickup_target_point_name = str(jobs[0].get("pickup_target_point_name", "") or "").strip().lower()
        workpiece_height_mm = float(jobs[0].get("workpiece_height_mm", 0.0) or 0.0)
        pickup_rx = float(pickup_pivot_pose[3]) if len(pickup_pivot_pose) >= 4 else 180.0
        pickup_ry = float(pickup_pivot_pose[4]) if len(pickup_pivot_pose) >= 5 else 0.0
        pickup_motion = owner._paint_process_config().pickup_motion

        pickup_z = owner._pickup_z_mm
        if pickup_z is None:
            pickup_z = (
                owner._pickup_safety_z_min_mm
                + workpiece_height_mm
                + pickup_motion.contact_offset_mm
            )

        should_apply_tcp_offset = (
            bool(owner._contact_motion_config.apply_camera_to_tcp_for_pickup)
            and not pickup_target_point_name
        )
        if should_apply_tcp_offset:
            pickup_tcp_dx, pickup_tcp_dy = _camera_to_tcp_delta(
                owner._contact_motion_config.camera_to_tcp_x_offset,
                owner._contact_motion_config.camera_to_tcp_y_offset,
                pickup_rz,
            )
        else:
            pickup_tcp_dx, pickup_tcp_dy = 0.0, 0.0

        _logger.info(
            "[PICKUP] pickup_xy=(%.3f, %.3f) pickup_rz=%.3f pickup_rz_source=%s pickup_target=%s workpiece_height=%.3f pickup_z=%.3f safety_z_min=%.3f apply_tcp_offset=%s configured_tcp_offset=(%.3f, %.3f) rotated_tcp_offset=(%.3f, %.3f)",
            pickup_centroid_x,
            pickup_centroid_y,
            pickup_rz,
            "execution_plan",
            pickup_target_point_name or "camera",
            workpiece_height_mm,
            float(pickup_z),
            owner._pickup_safety_z_min_mm,
            should_apply_tcp_offset,
            owner._contact_motion_config.camera_to_tcp_x_offset,
            owner._contact_motion_config.camera_to_tcp_y_offset,
            pickup_tcp_dx,
            pickup_tcp_dy,
        )

        pickup_approach_z = float(pickup_z) + pickup_motion.approach_offset_mm
        pickup_lift_z = float(pickup_z) + min(
            pickup_motion.initial_lift_clearance_mm,
            pickup_motion.approach_offset_mm,
        )
        pickup_x = pickup_centroid_x - pickup_tcp_dx
        pickup_y = pickup_centroid_y - pickup_tcp_dy
        pickup_approach_pose = [pickup_x, pickup_y, pickup_approach_z, pickup_rx, pickup_ry, pickup_rz]
        lift_pose = [pickup_x, pickup_y, pickup_lift_z, pickup_rx, pickup_ry, pickup_rz]
        pickup_pose = [pickup_x, pickup_y, float(pickup_z), pickup_rx, pickup_ry, pickup_rz]

        if owner._contact_motion_config.motion_plane == "xz_y_ry":
            _logger.info(
                "[PICKUP] xz/ry handoff: mirrored=%s pickup_rz=%.3f first_pivot_ry=%.3f paint_reference_ry=%.3f align_rz=%.3f",
                owner._mirror_xz_ry_pickup_handoff,
                pickup_rz,
                float(first_pivot_pose[4]) if len(first_pivot_pose) >= 5 else pickup_ry,
                float(paint_pivot_pose[4]) if len(paint_pivot_pose) >= 5 else pickup_ry,
                align_rz,
            )

        align_pose = [pickup_x, pickup_y, pickup_approach_z, pickup_rx, pickup_ry, align_rz]
        change_plane_pose = [
            pickup_x,
            pickup_y,
            float(pickup_approach_z),
            float(paint_pivot_pose[3]) if len(paint_pivot_pose) >= 4 else pickup_rx,
            pickup_ry,
            align_rz,
        ]

        staged_pose = self._build_staged_pose(
            first_pivot_pose=first_pivot_pose,
            change_plane_pose=change_plane_pose,
            align_ry=pickup_ry,
            align_rz=align_rz,
        )
        safe_travel_waypoints = owner._resolve_safe_travel_waypoints()
        safe_travel_poses = [list(item["position"]) for item in safe_travel_waypoints]
        if bool(owner._paint_process_config().safe_travel.enabled) and not safe_travel_waypoints:
            return None
        if safe_travel_waypoints:
            _logger.info(
                "[PICKUP] safe travel waypoints configured: count=%d first=%s",
                len(safe_travel_waypoints),
                [round(float(v), 3) for v in safe_travel_waypoints[0]["position"][:6]],
            )

        return PickupTransferPlan(
            pickup_approach_pose=pickup_approach_pose,
            pickup_pose=pickup_pose,
            lift_pose=lift_pose,
            change_plane_pose=change_plane_pose,
            align_pose=align_pose,
            stage_transition_poses=[],
            staged_pose=staged_pose,
            paint_pivot_pose=list(paint_pivot_pose),
            safe_travel_poses=safe_travel_poses,
            safe_travel_waypoints=safe_travel_waypoints,
            source_rotation_deg=source_rotation_deg,
            projected_source_path=source_path,
            projected_pivot_path=projected_pivot_path,
            projected_snapshots=projected_snapshots,
            projected_diagnostics=projected_diagnostics,
        )

    def _log_anchor_offset(
        self,
        *,
        source_path: list[list[float]],
        first_pivot_pose: list[float],
        paint_pivot_pose: list[float],
        anchor_xy: tuple[float, float],
    ) -> None:
        owner = self._owner
        source_planar_i, source_planar_j = owner._contact_motion_config.source_planar_coordinate_indices
        planar_i, planar_j = owner._contact_motion_config.planar_coordinate_indices
        source_first = np.asarray(
            [
                float(source_path[0][source_planar_i]),
                float(source_path[0][source_planar_j]),
            ],
            dtype=float,
        )
        source_anchor = np.asarray([float(anchor_xy[0]), float(anchor_xy[1])], dtype=float)
        source_offset = source_first - source_anchor
        command_offset = np.asarray(
            [
                float(first_pivot_pose[planar_i]) - float(paint_pivot_pose[planar_i]),
                float(first_pivot_pose[planar_j]) - float(paint_pivot_pose[planar_j]),
            ],
            dtype=float,
        )
        _logger.info(
            "[PICKUP] pivot anchor offset: source_first=(%.3f, %.3f) source_anchor=(%.3f, %.3f) "
            "source_first_minus_anchor=(%.3f, %.3f) command_tcp_minus_pivot_%s%s=(%.3f, %.3f)",
            float(source_first[0]),
            float(source_first[1]),
            float(source_anchor[0]),
            float(source_anchor[1]),
            float(source_offset[0]),
            float(source_offset[1]),
            owner._contact_motion_config.planar_axes[0],
            owner._contact_motion_config.planar_axes[1],
            float(command_offset[0]),
            float(command_offset[1]),
        )

    def _build_staged_pose(
        self,
        *,
        first_pivot_pose: list[float],
        change_plane_pose: list[float],
        align_ry: float,
        align_rz: float,
    ) -> list[float]:
        owner = self._owner
        staged_pose = list(first_pivot_pose)
        _logger.debug("staged_pose = %s", staged_pose)
        if owner._contact_motion_config.motion_plane == "xy_z_rz" and len(staged_pose) >= 6:
            raw_staged_rz = float(staged_pose[5])
            staged_pose[5] = float(align_rz)
            _logger.info(
                "[PICKUP] xy/rz staged orientation restored: raw_rz=%.3f reference_rz=%.3f selected_rz=%.3f",
                raw_staged_rz,
                float(align_rz),
                float(staged_pose[5]),
            )
        elif owner._contact_motion_config.motion_plane == "xz_y_ry" and len(staged_pose) >= 6:
            raw_staged_ry = float(staged_pose[4])
            staged_pose[5] = float(align_rz)
            staged_pose[4] = float(change_plane_pose[4]) if len(change_plane_pose) >= 5 else float(align_ry)
            _logger.info(
                "[PICKUP] xz/ry stage axis selection: raw_ry=%.3f reference_ry=%.3f selected_ry=%.3f fixed_rz=%.3f initial_rotation_deferred=true",
                raw_staged_ry,
                float(align_ry),
                float(staged_pose[4]),
                float(align_rz),
            )
            _logger.info(
                "[PICKUP] xz/ry staged pose: first_pivot=%s change_plane=%s staged=%s",
                [round(float(v), 3) for v in first_pivot_pose[:6]],
                [round(float(v), 3) for v in change_plane_pose[:6]],
                [round(float(v), 3) for v in staged_pose[:6]],
            )
        return staged_pose

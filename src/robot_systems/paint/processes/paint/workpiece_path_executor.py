from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

import numpy as np

from src.applications.workpiece_editor.service.i_workpiece_path_executor import IWorkpiecePathExecutor
from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import PivotSimulationConfig, _PIVOT_TRANSLATION_AXIS_OFFSETS_DEG, \
    _PIVOT_SIDE_SIGNS, _PIVOT_TRANSLATION_DIRECTION_SIGNS, _PICKUP_APPROACH_OFFSET_MM, _PICKUP_DEFAULT_VEL_PERCENT, \
    _PICKUP_DEFAULT_ACC_PERCENT, _PICKUP_CONTACT_OFFSET_MM
from src.robot_systems.paint.processes.paint.pivot_projection import (
    project_pivot_motion_geometry,
    rebase_projected_pivot_path_to_zero_start_rz,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PickupToPivotPlan:
    """Concrete pickup and staging poses derived from one prepared execution plan."""
    pickup_approach_pose: list[float]
    pickup_pose: list[float]
    lift_pose: list[float]
    staged_pose: list[float]

def _normalize_pivot_config(
    *,
    translation_axis: str = "x",
    pivot_side: str = "negative",
    translation_direction: str = "forward",
    apply_camera_to_tcp_for_pickup: bool = False,
    camera_to_tcp_x_offset: float = 0.0,
    camera_to_tcp_y_offset: float = 0.0,
) -> PivotSimulationConfig:
    """Normalize user-facing pivot settings into a validated simulation config."""
    axis_key = str(translation_axis or "x").strip().lower()
    side_key = str(pivot_side or "negative").strip().lower()
    direction_key = str(translation_direction or "forward").strip().lower()
    return PivotSimulationConfig(
        translation_axis=axis_key if axis_key in _PIVOT_TRANSLATION_AXIS_OFFSETS_DEG else "x",
        pivot_side=side_key if side_key in _PIVOT_SIDE_SIGNS else "negative",
        translation_direction=(
            direction_key if direction_key in _PIVOT_TRANSLATION_DIRECTION_SIGNS else "forward"
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
        base_position_provider: Optional[Callable[[], Optional[list[float]]]] = None,
        post_execute_callback: Optional[Callable[[], bool]] = None,
        robot_config_provider: Optional[Callable[[], object]] = None,
        vacuum_pump=None,
        pickup_tool: int = 0,
        pickup_user: int = 0,
        pickup_z_mm: float | None = None,
        debug_dump_dir: str | None = None,
        pivot_translation_axis: str = "x",
        pivot_side: str = "negative",
        pivot_translation_direction: str = "forward",
        apply_camera_to_tcp_for_pickup: bool = False,
        camera_to_tcp_x_offset: float = 0.0,
        camera_to_tcp_y_offset: float = 0.0,
    ) -> None:
        """Store robot dependencies and initialize the pivot/pickup execution configuration."""
        self._robot_service = robot_service
        self._base_position_provider = base_position_provider
        self._post_execute_callback = post_execute_callback
        self._robot_config_provider = robot_config_provider
        self._vacuum_pump = vacuum_pump
        self._pickup_tool = int(pickup_tool)
        self._pickup_user = int(pickup_user)
        self._pickup_z_mm = None if pickup_z_mm is None else float(pickup_z_mm)
        self._pickup_safety_z_min_mm = 100.0
        self._debug_dump_dir = debug_dump_dir
        self._pivot_config = _normalize_pivot_config(
            translation_axis=pivot_translation_axis,
            pivot_side=pivot_side,
            translation_direction=pivot_translation_direction,
            apply_camera_to_tcp_for_pickup=apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=camera_to_tcp_y_offset,
        )

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
            translation_axis=self._pivot_config.translation_axis,
            pivot_side=self._pivot_config.pivot_side,
            translation_direction=self._pivot_config.translation_direction,
            apply_camera_to_tcp_for_pickup=self._pivot_config.apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=float(getattr(robot_config, "camera_to_tcp_x_offset", self._pivot_config.camera_to_tcp_x_offset)),
            camera_to_tcp_y_offset=float(getattr(robot_config, "camera_to_tcp_y_offset", self._pivot_config.camera_to_tcp_y_offset)),
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
            filepath = os.path.join(
                self._debug_dump_dir,
                f"pivot_trajectory_{safe_stage}_{safe_pattern}_{timestamp}.txt",
            )
            with open(filepath, "w", encoding="utf-8") as handle:
                handle.write(f"# Pivot trajectory dump\n# timestamp={timestamp}\n# pattern_type={pattern_type}\n# stage={stage}\n")
                if pivot_pose:
                    pose_values = ", ".join(f"{float(value):.6f}" for value in pivot_pose)
                    handle.write(f"# pivot_pose=[{pose_values}]\n")

                for section_name, path in (("SOURCE", source_path), ("PIVOT", pivot_path)):
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

    def get_supported_execution_modes(self) -> tuple[str, ...]:
        """Report the execution modes supported by the paint executor."""
        return ("pivot_path",)

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
            center_path, _, diagnostics = project_pivot_motion_geometry(
                source_path,
                pivot_pose,
                self._pivot_config,
            )
            self._write_pivot_debug_dump(
                source_path=source_path,
                pivot_path=center_path,
                diagnostics=diagnostics,
                pivot_pose=list(pivot_pose),
                pattern_type=str(job.get("pattern_type", "Path")),
                stage="preview",
            )
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
            _, snapshots, _ = project_pivot_motion_geometry(
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
        pivot_pose = self._resolve_base_position()
        if pivot_pose is None or len(pivot_pose) < 3:
            return None
        pivot_path, _, _ = project_pivot_motion_geometry(
            spline,
            pivot_pose,
            self._pivot_config,
        )
        _logger.debug("Simulated pivot path has %d points", len(pivot_path))
        if align_start_to_zero_rz:
            pivot_path = rebase_projected_pivot_path_to_zero_start_rz(pivot_path)
        return pivot_path

    def execute_preview_paths(
        self,
        execution_plan: WorkpieceExecutionPlan,
        mode: str = "continuous",
    ) -> tuple[bool, str]:
        """Execute a prepared plan by projecting each path into pivot motion and sending it to the robot."""
        jobs = execution_plan.execution_jobs
        if not jobs:
            return False, "No previewed paths available to execute"
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
            pivot_path, _, diagnostics = project_pivot_motion_geometry(
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
                "[EXECUTE] [RUN FROM PREVIEW] Sent %d waypoints to robot in %s mode (vel=%.0f acc=%.0f)",
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
        """Build pickup approach, pickup, lift, and staged pivot poses from the first execution job."""
        jobs = execution_plan.execution_jobs
        self._refresh_runtime_config()
        if not jobs:
            return None

        pivot_pose = self._resolve_base_position()
        if pivot_pose is None or len(pivot_pose) < 3:
            return None

        source_path = jobs[0].get("execution_path") or jobs[0].get("path") or []
        if not source_path:
            return None

        pivot_path, _, _ = project_pivot_motion_geometry(
            source_path,
            pivot_pose,
            self._pivot_config,
        )
        if not pivot_path:
            return None

        first_pivot_pose = list(pivot_path[0])
        pickup_target_point_name = str(
            jobs[0].get("pickup_target_point_name", "") or ""
        ).strip().lower()
        workpiece_height_mm = float(jobs[0].get("workpiece_height_mm", 0.0) or 0.0)
        pickup_xy = jobs[0].get("pickup_xy")
        if pickup_xy is not None and len(pickup_xy) >= 2:
            pickup_centroid_x = float(pickup_xy[0])
            pickup_centroid_y = float(pickup_xy[1])
        else:
            source_xy = np.array([
                [float(point[0]), float(point[1])]
                for point in source_path
                if len(point) >= 2
            ], dtype=float)
            if source_xy.size == 0:
                return None
            pickup_centroid_x = float(np.mean(source_xy[:, 0]))
            pickup_centroid_y = float(np.mean(source_xy[:, 1]))

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
            float(first_pivot_pose[3]),
            float(first_pivot_pose[4]),
            pickup_rz,
        ]
        pickup_pose = [
            pickup_centroid_x - pickup_tcp_dx,
            pickup_centroid_y - pickup_tcp_dy,
            float(pickup_z),
            float(first_pivot_pose[3]),
            float(first_pivot_pose[4]),
            pickup_rz,
        ]
        staged_pose = [
            float(first_pivot_pose[0]),
            float(first_pivot_pose[1]),
            pickup_approach_z,
            float(first_pivot_pose[3]),
            float(first_pivot_pose[4]),
            0.0,
        ]
        return PickupToPivotPlan(
            pickup_approach_pose=pickup_approach_pose,
            pickup_pose=pickup_pose,
            lift_pose=list(pickup_approach_pose),
            staged_pose=staged_pose,
        )

    def _move_pickup_phase(self, label: str, pose: list[float]) -> bool:
        """Execute one pickup-related robot move with the configured pickup tool and user."""
        _logger.info(
            "[PICKUP] %s tool=%d user=%d pose=%s",
            label,
            self._pickup_tool,
            self._pickup_user,
            [round(v, 3) for v in pose],
        )
        return self._robot_service.move_ptp(
            position=pose,
            tool=self._pickup_tool,
            user=self._pickup_user,
            velocity=_PICKUP_DEFAULT_VEL_PERCENT,
            acceleration=_PICKUP_DEFAULT_ACC_PERCENT,
            wait_to_reach=True,
        )

    def _turn_vacuum_on(self) -> tuple[bool, str]:
        """Enable the vacuum pump before pickup if one is configured."""
        if self._vacuum_pump is None:
            return True, ""
        _logger.info("[PICKUP] Turning vacuum pump ON before pickup")
        if self._vacuum_pump.turn_on():
            return True, ""
        return False, "Pickup approach succeeded, but vacuum pump ON failed"

    def _turn_vacuum_off(self) -> tuple[bool, str]:
        """Disable the vacuum pump after staging if one is configured."""
        if self._vacuum_pump is None:
            return True, ""
        _logger.info("[PICKUP] Turning vacuum pump OFF after staged pivot move")
        if self._vacuum_pump.turn_off():
            return True, ""
        return False, "Pickup succeeded, but vacuum pump OFF failed after pivot stage"

    def _run_post_execute_return(self, failure_message: str) -> tuple[bool, str]:
        """Run unwind and post-execution return logic after pivot painting finishes."""
        if self._post_execute_callback is None:
            return True, ""
        if not self._robot_service.unwind_joint6(
            blocking=True,
            queue_if_busy=True,
            vel=100.0,
            acc=100.0,
        ):
            return False, failure_message.format(reason="explicit unwind failed")
        try:
            moved = bool(self._post_execute_callback())
        except Exception:
            _logger.exception("[EXECUTE] Post-execute callback failed")
            return False, failure_message.format(reason="return-to-calibration failed")
        if not moved:
            return False, failure_message.format(reason="return-to-calibration failed")
        return True, ""

    def _execute_pivot_paths(self, execution_plan: WorkpieceExecutionPlan) -> tuple[bool, str, int]:
        """Execute all projected pivot paint paths in the prepared execution plan."""
        total_waypoints = 0
        for job in execution_plan.execution_jobs:
            spline = job.get("execution_path") or job.get("path") or []
            vel = float(job.get("vel", 10.0))
            acc = float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))
            if not spline:
                continue

            pivot_path = self._build_pivot_execution_path(spline, align_start_to_zero_rz=True)
            if not pivot_path:
                return False, "Pickup succeeded, but pivot-path geometry could not be built", total_waypoints

            result = self._robot_service.execute_trajectory(
                pivot_path,
                vel=vel,
                acc=acc,
                blocking=True,
                orientation_mode="per_waypoint",
            )
            if result not in (0, True, None):
                return False, f"Pickup succeeded, but {pattern_type} pivot paint failed with code {result}", total_waypoints
            total_waypoints += len(spline)
        return True, "", total_waypoints

    def execute_pickup_to_pivot(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[bool, str]:
        """Run the pickup-only sequence: approach, vacuum on, descend, lift, and stage at the pivot."""
        if self._robot_service is None:
            return False, "Robot service is not available"

        plan = self._build_pickup_and_stage_poses(execution_plan)
        if plan is None:
            return False, "Could not compute pickup-to-pivot poses"

        if not self._move_pickup_phase("Moving to pickup approach pose", plan.pickup_approach_pose):
            return False, "Pickup approach move failed"

        ok, msg = self._turn_vacuum_on()
        if not ok:
            return False, msg

        if not self._move_pickup_phase("Descending to pickup pose", plan.pickup_pose):
            return False, "Pickup descend move failed"

        if not self._move_pickup_phase("Lifting from pickup pose", plan.lift_pose):
            return False, "Pickup succeeded, but lift move failed"

        if not self._move_pickup_phase("Moving to staged pivot pose", plan.staged_pose):
            return False, "Pickup succeeded, but move-to-pivot failed"

        ok, msg = self._turn_vacuum_off()
        if not ok:
            return False, msg
        return True, "Pickup completed and staged at pivot-aligned first point"

    def execute_pickup_and_pivot_paint(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[bool, str]:
        """Run pickup, staging, projected pivot paint execution, and post-run return."""
        ok, msg = self.execute_pickup_to_pivot(execution_plan)
        if not ok:
            return False, msg

        ok, msg, total_waypoints = self._execute_pivot_paths(execution_plan)
        if not ok:
            return False, msg

        ok, msg = self._run_post_execute_return(
            "Pickup and pivot paint finished, but {reason}"
        )
        if not ok:
            return False, msg

        return True, (
            f"Pickup, alignment, and pivot paint completed "
            f"for {len(execution_plan.execution_jobs)} path(s), {total_waypoints} waypoints"
        )

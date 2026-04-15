from __future__ import annotations

import logging
from typing import Callable, Optional

import numpy as np

from src.applications.workpiece_editor.service.i_workpiece_path_executor import IWorkpiecePathExecutor

_logger = logging.getLogger(__name__)
_PIVOT_SIDE_PERPENDICULAR_DEG = 90.0
_PIVOT_SMOOTH_MAX_LINEAR_STEP_MM = 1.0
_PIVOT_SMOOTH_MAX_ANGULAR_STEP_DEG = 0.2
_PICKUP_DEFAULT_Z_MM = 300.0
_PICKUP_DEFAULT_VEL_PERCENT = 20.0
_PICKUP_DEFAULT_ACC_PERCENT = 20.0


def _rotate_xy_about(point_xy: tuple[float, float], angle_degrees: float, pivot_xy: tuple[float, float]) -> tuple[float, float]:
    angle_rad = float(np.radians(angle_degrees))
    cos_a = float(np.cos(angle_rad))
    sin_a = float(np.sin(angle_rad))
    px, py = float(point_xy[0]), float(point_xy[1])
    ox, oy = float(pivot_xy[0]), float(pivot_xy[1])
    dx = px - ox
    dy = py - oy
    return (
        ox + cos_a * dx - sin_a * dy,
        oy + sin_a * dx + cos_a * dy,
    )


def _unwrap_degrees(previous: float, current: float) -> float:
    value = float(current)
    prev = float(previous)
    while value - prev > 180.0:
        value -= 360.0
    while value - prev < -180.0:
        value += 360.0
    return value


def _densify_pose_path(
    poses: list[list[float]],
    max_linear_step_mm: float = _PIVOT_SMOOTH_MAX_LINEAR_STEP_MM,
    max_angular_step_deg: float = _PIVOT_SMOOTH_MAX_ANGULAR_STEP_DEG,
) -> list[list[float]]:
    if len(poses) < 2:
        return [list(pose) for pose in poses]

    densified: list[list[float]] = [list(poses[0])]
    max_linear_step_mm = max(float(max_linear_step_mm), 1e-3)
    max_angular_step_deg = max(float(max_angular_step_deg), 1e-3)

    for target_pose in poses[1:]:
        start_pose = densified[-1]
        end_pose = list(target_pose)
        dx = float(end_pose[0]) - float(start_pose[0])
        dy = float(end_pose[1]) - float(start_pose[1])
        dz = float(end_pose[2]) - float(start_pose[2])
        linear_distance = float(np.sqrt(dx * dx + dy * dy + dz * dz))
        angular_delta = abs(_unwrap_degrees(float(start_pose[5]), float(end_pose[5])) - float(start_pose[5]))
        steps = max(1, int(np.ceil(max(
            linear_distance / max_linear_step_mm,
            angular_delta / max_angular_step_deg,
        ))))

        previous_rz = float(start_pose[5])
        target_rz = _unwrap_degrees(previous_rz, float(end_pose[5]))
        for step_index in range(1, steps + 1):
            ratio = step_index / steps
            interpolated = [
                float(start_pose[0]) + dx * ratio,
                float(start_pose[1]) + dy * ratio,
                float(start_pose[2]) + dz * ratio,
                float(start_pose[3]) + (float(end_pose[3]) - float(start_pose[3])) * ratio,
                float(start_pose[4]) + (float(end_pose[4]) - float(start_pose[4])) * ratio,
                previous_rz + (target_rz - previous_rz) * ratio,
            ]
            densified.append(interpolated)

    return densified


def _rebase_pivot_path_to_zero_start_rz(path: list[list[float]]) -> list[list[float]]:
    if not path:
        return []
    rebased = [list(pose) for pose in path]
    start_rz = float(rebased[0][5]) if len(rebased[0]) >= 6 else 0.0
    for pose in rebased:
        if len(pose) >= 6:
            pose[5] = _unwrap_degrees(0.0, float(pose[5]) - start_rz)
    return rebased


def _simulate_pivot_projected_motion(
    path: list[list[float]],
    pivot_pose: list[float],
) -> tuple[list[list[float]], list[np.ndarray]]:
    if not path:
        return [], []
    if len(path) == 1:
        return [list(path[0])], [np.array([[float(path[0][0]), float(path[0][1])]], dtype=float)]

    pivot_x = float(pivot_pose[0])
    pivot_y = float(pivot_pose[1])
    pivot_z = float(pivot_pose[2]) if len(pivot_pose) >= 3 else float(path[0][2])
    rx = float(pivot_pose[3]) if len(pivot_pose) >= 4 else float(path[0][3])
    ry = float(pivot_pose[4]) if len(pivot_pose) >= 5 else float(path[0][4])
    base_rz = float(pivot_pose[5]) if len(pivot_pose) >= 6 else float(path[0][5])
    # Use the opposite perpendicular branch so the pivot path runs on the
    # other side of the pivot relative to the previous paint behavior.
    paint_axis_heading = base_rz + _PIVOT_SIDE_PERPENDICULAR_DEG

    points = np.array([[float(point[0]), float(point[1])] for point in path], dtype=float)
    if len(points) < 2:
        return (
            [[float(points[0][0]), float(points[0][1]), pivot_z, rx, ry, base_rz]],
            [points.copy()],
        )

    def _centroid_xy(current_points: np.ndarray) -> tuple[float, float]:
        return (float(np.mean(current_points[:, 0])), float(np.mean(current_points[:, 1])))

    def _rotate_shape(current_points: np.ndarray, angle_deg: float, pivot_xy: tuple[float, float]) -> np.ndarray:
        return np.array(
            [_rotate_xy_about((float(point[0]), float(point[1])), angle_deg, pivot_xy) for point in current_points],
            dtype=float,
        )

    def _segment_heading_deg(point_a: np.ndarray, point_b: np.ndarray) -> float:
        dx = float(point_b[0] - point_a[0])
        dy = float(point_b[1] - point_a[1])
        return float(np.degrees(np.arctan2(dy, dx)))

    pivot_xy = (pivot_x, pivot_y)
    initial_heading = _segment_heading_deg(points[0], points[1])
    initial_rotation = _unwrap_degrees(0.0, paint_axis_heading - initial_heading)
    points = _rotate_shape(points, initial_rotation, (float(points[0][0]), float(points[0][1])))
    translate_to_pivot = np.array([pivot_x - float(points[0][0]), pivot_y - float(points[0][1])], dtype=float)
    points = points + translate_to_pivot

    current_rz = _unwrap_degrees(base_rz, base_rz + initial_rotation)
    result: list[list[float]] = []
    snapshots: list[np.ndarray] = []
    center_xy = _centroid_xy(points)
    result.append([center_xy[0], center_xy[1], pivot_z, rx, ry, current_rz])
    snapshots.append(points.copy())

    axis_vector = np.array(
        [
            float(np.cos(np.radians(paint_axis_heading))),
            float(np.sin(np.radians(paint_axis_heading))),
        ],
        dtype=float,
    )

    for index in range(len(points) - 1):
        current_point = points[index]
        next_point = points[index + 1]
        segment_length = float(np.linalg.norm(next_point - current_point))
        if segment_length <= 1e-9:
            center_xy = _centroid_xy(points)
            result.append([center_xy[0], center_xy[1], pivot_z, rx, ry, current_rz])
            snapshots.append(points.copy())
            continue

        segment_heading = _segment_heading_deg(current_point, next_point)
        rotation_delta = _unwrap_degrees(0.0, paint_axis_heading - segment_heading)
        if abs(rotation_delta) > 1e-9:
            points = _rotate_shape(points, rotation_delta, pivot_xy)
            current_rz = _unwrap_degrees(current_rz, current_rz + rotation_delta)

        points = points - axis_vector * segment_length
        center_xy = _centroid_xy(points)
        result.append([center_xy[0], center_xy[1], pivot_z, rx, ry, current_rz])
        snapshots.append(points.copy())

    result = result[:len(path)]
    snapshots = snapshots[:len(path)]
    densified_result = _densify_pose_path(result)
    return densified_result, snapshots


class PaintWorkpiecePathExecutor(IWorkpiecePathExecutor):
    def __init__(
        self,
        robot_service,
        base_position_provider: Optional[Callable[[], Optional[list[float]]]] = None,
        post_execute_callback: Optional[Callable[[], bool]] = None,
        pickup_tool: int = 0,
        pickup_user: int = 0,
        pickup_z_mm: float | None = None,
    ) -> None:
        self._robot_service = robot_service
        self._base_position_provider = base_position_provider
        self._post_execute_callback = post_execute_callback
        self._pickup_tool = int(pickup_tool)
        self._pickup_user = int(pickup_user)
        self._pickup_z_mm = None if pickup_z_mm is None else float(pickup_z_mm)

    def get_supported_execution_modes(self) -> tuple[str, ...]:
        return ("pivot_path",)

    def supports_pickup_to_pivot(self) -> bool:
        return True

    def _resolve_base_position(self) -> Optional[list[float]]:
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
        execution_preview_jobs: list[dict],
    ) -> tuple[list[list[list[float]]], list[float] | None]:
        pivot_pose = self._resolve_base_position()
        if pivot_pose is None or len(pivot_pose) < 3:
            return [], pivot_pose
        paths = []
        for job in execution_preview_jobs:
            source_path = job.get("execution_path") or job.get("path") or []
            if not source_path:
                continue
            center_path, _ = _simulate_pivot_projected_motion(source_path, pivot_pose)
            paths.append(center_path)
        return paths, list(pivot_pose)

    def get_pivot_motion_preview(
        self,
        execution_preview_jobs: list[dict],
    ) -> tuple[list[list[np.ndarray]], list[float] | None]:
        pivot_pose = self._resolve_base_position()
        if pivot_pose is None or len(pivot_pose) < 3:
            return [], pivot_pose
        motion = []
        for job in execution_preview_jobs:
            source_path = job.get("execution_path") or job.get("path") or []
            if not source_path:
                continue
            _, snapshots = _simulate_pivot_projected_motion(source_path, pivot_pose)
            motion.append(snapshots)
        return motion, list(pivot_pose)

    def _build_pickup_and_stage_poses(
        self,
        execution_preview_jobs: list[dict],
    ) -> tuple[list[float], list[float]] | tuple[None, None]:
        if not execution_preview_jobs:
            return None, None

        pivot_pose = self._resolve_base_position()
        if pivot_pose is None or len(pivot_pose) < 3:
            return None, None

        source_path = execution_preview_jobs[0].get("execution_path") or execution_preview_jobs[0].get("path") or []
        if not source_path:
            return None, None

        pivot_path, _ = _simulate_pivot_projected_motion(source_path, pivot_pose)
        if not pivot_path:
            return None, None

        first_pivot_pose = list(pivot_path[0])
        source_xy = np.array([
            [float(point[0]), float(point[1])]
            for point in source_path
            if len(point) >= 2
        ], dtype=float)
        if source_xy.size == 0:
            return None, None
        pickup_centroid_x = float(np.mean(source_xy[:, 0]))
        pickup_centroid_y = float(np.mean(source_xy[:, 1]))

        pickup_z = self._pickup_z_mm
        if pickup_z is None:
            pickup_z = float(pivot_pose[2]) if len(pivot_pose) >= 3 else _PICKUP_DEFAULT_Z_MM

        # Pick up at the workpiece centroid with the inverse of the first pivot
        # orientation so that after the robot returns to RZ=0 the workpiece's
        # first point is already aligned with the pivot-path start.
        pickup_rz = _unwrap_degrees(0.0, -float(first_pivot_pose[5]))
        pickup_pose = [
            pickup_centroid_x,
            pickup_centroid_y,
            float(pickup_z),
            float(first_pivot_pose[3]),
            float(first_pivot_pose[4]),
            pickup_rz,
        ]
        staged_pose = [
            float(first_pivot_pose[0]),
            float(first_pivot_pose[1]),
            float(pickup_z),
            float(first_pivot_pose[3]),
            float(first_pivot_pose[4]),
            0.0,
        ]
        return pickup_pose, staged_pose

    def _build_pivot_execution_path(
        self,
        spline: list[list[float]],
        *,
        align_start_to_zero_rz: bool = False,
    ) -> list[list[float]] | None:
        pivot_pose = self._resolve_base_position()
        if pivot_pose is None or len(pivot_pose) < 3:
            return None
        pivot_path, _ = _simulate_pivot_projected_motion(spline, pivot_pose)
        if align_start_to_zero_rz:
            pivot_path = _rebase_pivot_path_to_zero_start_rz(pivot_path)
        return pivot_path

    def execute_preview_paths(
        self,
        execution_preview_jobs: list[dict],
        mode: str = "continuous",
    ) -> tuple[bool, str]:
        if not execution_preview_jobs:
            return False, "No previewed paths available to execute"
        if self._robot_service is None:
            return False, "Robot service is not available"

        mode = str(mode or "continuous").strip().lower()
        if mode != "pivot_path":
            return False, f"Unsupported paint execution mode: {mode}"

        total_waypoints = 0
        for job in execution_preview_jobs:
            spline = job.get("execution_path") or job.get("path") or []
            vel = float(job.get("vel", 60.0))
            acc = float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))
            if not spline:
                continue

            pivot_path = self._build_pivot_execution_path(spline, align_start_to_zero_rz=False)
            if not pivot_path:
                return False, "Pivot-path execution requires a valid base/pivot position"
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
            f"Executed {len(execution_preview_jobs)} path(s), "
            f"{total_waypoints} waypoints in {mode} mode"
        )

    def execute_pickup_to_pivot(
        self,
        execution_preview_jobs: list[dict],
    ) -> tuple[bool, str]:
        if self._robot_service is None:
            return False, "Robot service is not available"

        pickup_pose, staged_pose = self._build_pickup_and_stage_poses(execution_preview_jobs)
        if pickup_pose is None or staged_pose is None:
            return False, "Could not compute pickup-to-pivot poses"

        _logger.info(
            "[PICKUP] Moving to pickup pose tool=%d user=%d pose=%s",
            self._pickup_tool,
            self._pickup_user,
            [round(v, 3) for v in pickup_pose],
        )
        pickup_ok = self._robot_service.move_ptp(
            position=pickup_pose,
            tool=self._pickup_tool,
            user=self._pickup_user,
            velocity=_PICKUP_DEFAULT_VEL_PERCENT,
            acceleration=_PICKUP_DEFAULT_ACC_PERCENT,
            wait_to_reach=True,
        )
        if not pickup_ok:
            return False, "Pickup move failed"

        _logger.info(
            "[PICKUP] Moving to staged pivot pose tool=%d user=%d pose=%s",
            self._pickup_tool,
            self._pickup_user,
            [round(v, 3) for v in staged_pose],
        )
        stage_ok = self._robot_service.move_ptp(
            position=staged_pose,
            tool=self._pickup_tool,
            user=self._pickup_user,
            velocity=_PICKUP_DEFAULT_VEL_PERCENT,
            acceleration=_PICKUP_DEFAULT_ACC_PERCENT,
            wait_to_reach=True,
        )
        if not stage_ok:
            return False, "Pickup succeeded, but move-to-pivot failed"

        return True, "Pickup completed and staged at pivot-aligned first point"

    def execute_pickup_and_pivot_paint(
        self,
        execution_preview_jobs: list[dict],
    ) -> tuple[bool, str]:
        ok, msg = self.execute_pickup_to_pivot(execution_preview_jobs)
        if not ok:
            return False, msg

        total_waypoints = 0
        for job in execution_preview_jobs:
            spline = job.get("execution_path") or job.get("path") or []
            vel = float(job.get("vel", 60.0))
            acc = float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))
            if not spline:
                continue

            pivot_path = self._build_pivot_execution_path(spline, align_start_to_zero_rz=True)
            if not pivot_path:
                return False, "Pickup succeeded, but pivot-path geometry could not be built"

            result = self._robot_service.execute_trajectory(
                pivot_path,
                vel=vel,
                acc=acc,
                blocking=True,
                orientation_mode="per_waypoint",
            )
            if result not in (0, True, None):
                return False, f"Pickup succeeded, but {pattern_type} pivot paint failed with code {result}"
            total_waypoints += len(spline)

        if self._post_execute_callback is not None:
            if not self._robot_service.unwind_joint6(
                blocking=True,
                queue_if_busy=True,
                vel=100.0,
                acc=100.0,
            ):
                return False, "Pickup and pivot paint finished, but explicit unwind failed"
            try:
                moved = bool(self._post_execute_callback())
            except Exception:
                _logger.exception("[EXECUTE] Post-execute callback failed")
                return False, "Pickup and pivot paint finished, but return-to-calibration failed"
            if not moved:
                return False, "Pickup and pivot paint finished, but return-to-calibration failed"

        return True, (
            f"Pickup, alignment, and pivot paint completed "
            f"for {len(execution_preview_jobs)} path(s), {total_waypoints} waypoints"
        )

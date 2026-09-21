from __future__ import annotations

import logging
from dataclasses import replace

import numpy as np

from src.engine.robot.motion_sequence import (
    OrderedMotionCommand,
    OrderedMotionType,
    OrderedPathCommand,
    OrderedPositionCommand,
)
from src.robot_systems.paint.timing import timed_step
from src.robot_systems.paint.processes.paint.motion.pose_sampling import (
    FreshPoseReadError,
    read_fresh_pose,
)

_logger = logging.getLogger(__name__)

_PICKUP_RESUME_WAYPOINT_TOLERANCE_MM = 2.0


class PaintMotionExecutor:
    """Shared robot motion and vacuum operations for paint execution handlers."""

    def __init__(self, owner) -> None:
        self._owner = owner
        self._ordered_chain_resume_start_index: int | None = None
        self._ordered_chain_interrupted_by_pause: bool = False
        self.last_motion_error: str | None = None

    @timed_step(_logger, "pickup_phase", label_arg="label")
    def move_pickup_phase(
        self,
        label: str,
        pose: list[float],
        *,
        velocity: float,
        acceleration: float,
        motion_type: OrderedMotionType = OrderedMotionType.PTP,
        blendR: float = 0.0,
        corridor_id: str | None = None,
    ) -> bool:
        """Execute one carried-workpiece robot move with explicit motion limits."""
        if velocity is None or acceleration is None:
            raise ValueError(f"Pickup phase '{label}' requires explicit velocity and acceleration")
        if not isinstance(motion_type, OrderedMotionType):
            raise TypeError("motion_type must be an OrderedMotionType")
        owner = self._owner
        _logger.info(
            "[PICKUP] %s tool=%d user=%d pose=%s",
            label,
            owner._pickup_tool,
            owner._pickup_user,
            [round(v, 3) for v in pose],
        )
        while True:
            if corridor_id is not None:
                ok = owner._robot_service.move_linear_in_corridor(
                    corridor_id=corridor_id,
                    position=pose,
                    tool=owner._pickup_tool,
                    user=owner._pickup_user,
                    velocity=velocity,
                    acceleration=acceleration,
                    blendR=max(0.0, float(blendR)),
                    wait_to_reach=True,
                )
            elif motion_type is OrderedMotionType.FAST_LINEAR:
                result = owner._robot_service.move_fast_linear(
                    position=pose,
                    tool=owner._pickup_tool,
                    user=owner._pickup_user,
                    vel=velocity,
                    acc=acceleration,
                    trajectory_optimizer="TOTG",
                )
                ok = bool(
                    isinstance(result, dict)
                    and result.get("result") == 0
                    and result.get("success") is True
                    and result.get("accepted") is True
                    and result.get("final") is True
                    and result.get("queued") is False
                )
            elif motion_type is OrderedMotionType.LINEAR:
                ok = owner._robot_service.move_linear(
                    position=pose,
                    tool=owner._pickup_tool,
                    user=owner._pickup_user,
                    velocity=velocity,
                    acceleration=acceleration,
                    blendR=max(0.0, float(blendR)),
                    wait_to_reach=True,
                )
            else:
                ok = owner._robot_service.move_ptp(
                    position=pose,
                    tool=owner._pickup_tool,
                    user=owner._pickup_user,
                    velocity=velocity,
                    acceleration=acceleration,
                    wait_to_reach=True,
                )
            if ok:
                return True
            if not self.resume_after_interrupted_non_contact_motion(label):
                return False

    @timed_step(_logger, "pickup_phase", label_arg="label")
    def move_ordered_pickup_sequence(self, label: str, segments: list[OrderedMotionCommand]) -> bool:
        """Execute a pickup sequence as ordered robot motion segments."""
        owner = self._owner
        _logger.info(
            "[PICKUP] %s tool=%d user=%d segments=%d",
            label,
            owner._pickup_tool,
            owner._pickup_user,
            len(segments),
        )
        if any(
            isinstance(segment, OrderedPositionCommand)
            and segment.motion_type is OrderedMotionType.FAST_LINEAR
            for segment in segments
        ):
            return self._move_mixed_pickup_sequence(label, segments)
        active_segments = list(segments)
        while active_segments:
            result = owner._robot_service.execute_ordered_motion_chain(
                segments=active_segments,
                tool=owner._pickup_tool,
                user=owner._pickup_user,
                blocking=True,
            )
            if result in (0, True, None):
                self.last_motion_error = None
                return True
            self.last_motion_error = owner._robot_service.get_last_motion_error()
            if self.last_motion_error:
                _logger.error("[PICKUP] Ordered motion chain rejected: %s", self.last_motion_error)
            if not self.resume_after_interrupted_non_contact_motion(label):
                return False
            active_segments = self.trim_ordered_pickup_segments_from_current_pose(active_segments)
        return True

    def _move_mixed_pickup_sequence(self, label: str, segments: list[OrderedMotionCommand]) -> bool:
        """Execute ordered-compatible chunks around explicit Fast LIN moves."""
        ordered_chunk: list[OrderedMotionCommand] = []

        def flush_ordered_chunk() -> bool:
            if not ordered_chunk:
                return True
            chunk = list(ordered_chunk)
            terminal = chunk[-1]
            if isinstance(terminal, (OrderedPositionCommand, OrderedPathCommand)):
                chunk[-1] = replace(
                    terminal,
                    profile=replace(terminal.profile, blend_radius=0.0),
                )
            ordered_chunk.clear()
            return self.move_ordered_pickup_sequence(f"{label} (ordered chunk)", chunk)

        for segment in segments:
            if not (
                isinstance(segment, OrderedPositionCommand)
                and segment.motion_type is OrderedMotionType.FAST_LINEAR
            ):
                ordered_chunk.append(segment)
                continue
            if not flush_ordered_chunk():
                return False
            if not self.move_pickup_phase(
                segment.label or label,
                list(segment.position),
                velocity=float(segment.profile.velocity_percent),
                acceleration=float(segment.profile.acceleration_percent),
                motion_type=OrderedMotionType.FAST_LINEAR,
                blendR=0.0,
            ):
                return False
        return flush_ordered_chunk()

    def pause_current_execution(self) -> None:
        owner = self._owner
        control = owner._active_execution_control
        if control is not None and control.in_protected_phase():
            return
        ordered_status = self.read_ordered_motion_chain_status()
        if self.ordered_motion_chain_segment_is_protected(ordered_status):
            _logger.info("[EXECUTE] Paint pause requested during protected ordered segment; deferring stop")
            return
        self._ordered_chain_resume_start_index = self.ordered_motion_chain_resume_index(ordered_status)
        self._ordered_chain_interrupted_by_pause = True
        try:
            owner._robot_service.stop_motion()
        except Exception:
            _logger.exception("[EXECUTE] Failed to stop robot motion during paint pause")
            raise

    def read_ordered_motion_chain_status(self) -> dict | None:
        try:
            status = self._owner._robot_service.get_execution_status()
        except Exception:
            _logger.exception("[EXECUTE] Failed to read ordered motion status during paint pause")
            return None
        if not isinstance(status, dict):
            return None
        ordered = status.get("ordered_motion_chain")
        if not isinstance(ordered, dict):
            return None
        return ordered

    @staticmethod
    def ordered_motion_chain_segment_is_protected(ordered: dict | None) -> bool:
        if not isinstance(ordered, dict):
            return False
        return bool(
            ordered.get("active")
            and ordered.get("phase") == "executing"
            and ordered.get("current_segment_protected")
        )

    @staticmethod
    def ordered_motion_chain_resume_index(ordered: dict | None) -> int:
        if not isinstance(ordered, dict) or not ordered.get("active"):
            return 0
        try:
            index = int(ordered.get("current_segment_index"))
        except (TypeError, ValueError):
            return 0
        return max(0, index)

    def resume_after_interrupted_non_contact_motion(self, label: str) -> bool:
        owner = self._owner
        control = owner._active_execution_control
        interrupted_by_pause = self._ordered_chain_interrupted_by_pause
        if (control is None or not control.pause_requested()) and not interrupted_by_pause:
            return False
        _logger.info("[EXECUTE] Paused during non-contact motion '%s'; waiting to resume", label)
        return owner._wait_for_paint_resume(control)

    def consume_ordered_chain_resume_start_index(self) -> int | None:
        start_index = self._ordered_chain_resume_start_index
        self._ordered_chain_resume_start_index = None
        return start_index

    def mark_ordered_chain_interrupted_by_pause(self, interrupted: bool) -> None:
        self._ordered_chain_interrupted_by_pause = bool(interrupted)

    def trim_ordered_pickup_segments_from_current_pose(
        self,
        segments: list[OrderedMotionCommand],
    ) -> list[OrderedMotionCommand]:
        """Skip already-passed pickup waypoints after pause/resume."""
        if not segments:
            return []

        current = self._read_current_robot_pose()
        if current is None:
            _logger.warning("[PICKUP] Resume requested but current robot pose is unavailable; reusing full sequence")
            return segments

        target_positions = []
        for segment in segments:
            if isinstance(segment, OrderedPathCommand):
                target_positions.append(list(segment.path[-1]))
            elif isinstance(segment, OrderedPositionCommand):
                target_positions.append(list(segment.position))
        if not target_positions:
            return segments

        current_xyz = np.asarray(current[:3], dtype=float)
        targets_xyz = [np.asarray(target[:3], dtype=float) for target in target_positions if len(target) >= 3]
        if not targets_xyz:
            return segments

        best_index = min(
            range(len(targets_xyz)),
            key=lambda index: float(np.linalg.norm(current_xyz - targets_xyz[index])),
        )
        for index in range(max(0, best_index - 1), min(len(targets_xyz) - 1, best_index + 1) + 1):
            distance = self._point_to_segment_distance(
                current_xyz,
                targets_xyz[index],
                targets_xyz[index + 1],
            )
            if distance <= _PICKUP_RESUME_WAYPOINT_TOLERANCE_MM:
                best_index = index + 1
                break

        start_index = min(best_index + 1, len(segments) - 1)
        _logger.info(
            "[PICKUP] Resuming ordered sequence from segment %d/%d current=%s",
            start_index + 1,
            len(segments),
            [round(float(value), 3) for value in current[:6]],
        )
        return segments[start_index:]

    def _read_current_robot_pose(self) -> list[float] | None:
        try:
            pose = read_fresh_pose(
                self._owner._robot_service,
                error_message="Failed to read fresh robot pose for ordered resume",
            )
        except FreshPoseReadError as exc:
            _logger.error("[PICKUP] %s", exc)
            return None
        return pose

    @staticmethod
    def _point_to_segment_distance(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> float:
        segment = end - start
        length_sq = float(np.dot(segment, segment))
        if length_sq <= 1e-12:
            return float(np.linalg.norm(point - start))
        t = float(np.dot(point - start, segment) / length_sq)
        t = max(0.0, min(1.0, t))
        projection = start + t * segment
        return float(np.linalg.norm(point - projection))

    @timed_step(_logger, "vacuum_on")
    def turn_vacuum_on(self, *, required: bool = False) -> tuple[bool, str]:
        """Enable the vacuum pump before pickup if one is configured."""
        owner = self._owner
        if not owner._is_vacuum_pump_enabled():
            if required:
                _logger.error("[PICKUP] Vacuum pump is required but disabled; refusing to start motion")
                return False, "Servo-contact pickup requires the vacuum pump to be enabled"
            _logger.info("[PICKUP] Vacuum pump ON skipped: disabled by configuration")
            return True, ""
        if owner._vacuum_pump is None:
            if required:
                _logger.error("[PICKUP] Vacuum pump is required but unavailable; refusing to start motion")
                return False, "Servo-contact pickup requires an available vacuum pump"
            _logger.info("[PICKUP] Vacuum pump ON skipped: pump not configured")
            return True, ""
        _logger.info("[PICKUP] Turning vacuum pump ON before pickup")
        try:
            enabled = bool(owner._vacuum_pump.turn_on())
        except Exception:
            _logger.exception("[PICKUP] Vacuum pump ON command failed; refusing to start motion")
            return False, "Vacuum pump ON command failed; pickup motion was not started"
        if enabled:
            return True, ""
        return False, "Vacuum pump failed to turn on; pickup motion was not started"

    @timed_step(_logger, "vacuum_off")
    def turn_vacuum_off(self) -> tuple[bool, str]:
        """Disable the vacuum pump after staging if one is configured."""
        owner = self._owner
        if not owner._is_vacuum_pump_enabled():
            _logger.info("[PICKUP] Vacuum pump OFF skipped: disabled by configuration")
            return True, ""
        if owner._vacuum_pump is None:
            _logger.info("[PICKUP] Vacuum pump OFF skipped: pump not configured")
            return True, ""
        _logger.info("[PICKUP] Turning vacuum pump OFF after staged pivot move")
        if owner._vacuum_pump.turn_off():
            return True, ""
        return False, "Pickup succeeded, but vacuum pump OFF failed after pivot stage"

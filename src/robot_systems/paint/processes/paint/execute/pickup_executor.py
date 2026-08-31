from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from src.engine.robot.enums.axis import Direction, RobotAxis
from src.engine.robot.procedures import (
    ServoRetractConfig,
    ServoUntilConditionConfig,
    ServoUntilConditionProcedure,
)
from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import (
    PICKUP_CONTACT_MODE_HEIGHT_MEASURE,
    PICKUP_CONTACT_MODE_PLANNED,
    PICKUP_CONTACT_MODE_SERVO_CONTACT,
    PICKUP_CONTACT_MODES,
)
from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.magazine_load_result import (
    NO_WORKPIECE_AT_CALIBRATION,
)
from src.robot_systems.paint.timing import timed_block, timed_step

_logger = logging.getLogger(__name__)


def pickup_pose_is_close(
    actual_pose: object,
    target_pose: object,
    *,
    position_tolerance_mm: float = 0.5,
    orientation_tolerance_deg: float = 0.5,
) -> bool:
    """Return True when a recovery move would be an effective no-op."""
    try:
        actual = [float(value) for value in list(actual_pose)[:6]]
        target = [float(value) for value in list(target_pose)[:6]]
    except (TypeError, ValueError):
        return False
    if len(actual) != 6 or len(target) != 6:
        return False
    position_error = math.sqrt(sum((actual[index] - target[index]) ** 2 for index in range(3)))
    orientation_error = max(
        abs((actual[index] - target[index] + 180.0) % 360.0 - 180.0)
        for index in range(3, 6)
    )
    return position_error <= position_tolerance_mm and orientation_error <= orientation_tolerance_deg


def pickup_condition_is_active_after_retract(condition: object) -> bool:
    """Return whether the picked workpiece remains detected after Servo retract."""
    try:
        reader = getattr(condition, "is_active", None)
        active = reader() if callable(reader) else condition()
    except Exception:
        _logger.exception("[PICKUP] Pickup condition read failed after Servo retract")
        return False
    if not bool(active):
        _logger.error("[PICKUP] Workpiece is no longer detected after Servo retract")
        return False
    _logger.info("[PICKUP] Workpiece detection verified after Servo retract")
    return True


@dataclass(frozen=True)
class PickupWaypoint:
    """One carried-part pickup or staging move."""

    label: str
    pose: list[float]
    vel_percent: float
    acc_percent: float
    motion_type: str | None = None
    blendR: float | None = None


@dataclass(frozen=True)
class PickupPlan:
    """Resolved pickup sequence for moving the workpiece to the paint start."""

    strategy_name: str
    motion_plan: object
    waypoints: tuple[PickupWaypoint, ...]
    vacuum_on_before_moves: bool = True
    change_plane_combined_with_first_contact: bool = False
    contact_mode: str = PICKUP_CONTACT_MODE_PLANNED
    contact_waypoint_index: int | None = None
    retract_reference_pose: list[float] | None = None


def normalize_pickup_contact_mode(value: object) -> str:
    return str(value or PICKUP_CONTACT_MODE_PLANNED).strip().lower()


class PaintPickupStrategy(Protocol):
    """Build paint pickup/staging plans without exposing strategy details to the main executor."""

    name: str

    def build_plan(self, owner, prepared_workpiece: WorkpieceExecutionPlan) -> PickupPlan | None:
        """Return the ordered pickup actions for the active workpiece."""


class DefaultPickupStrategy:
    """Default strategy for calibration-table pickup, align, and pivot staging."""

    name = "default"

    def build_plan(self, owner, prepared_workpiece: WorkpieceExecutionPlan) -> PickupPlan | None:
        motion_plan = owner._pickup_transfer_planner.build_plan(prepared_workpiece)
        if motion_plan is None:
            return None

        pickup_motion = owner._paint_process_config().pickup_motion
        combine_change_plane = pickup_motion.combine_change_plane_with_first_contact
        waypoints: list[PickupWaypoint] = [
            PickupWaypoint(
                "Moving to pickup approach pose",
                list(motion_plan.pickup_approach_pose),
                pickup_motion.approach_vel_percent,
                pickup_motion.approach_acc_percent,
                pickup_motion.approach_motion_type,
                pickup_motion.approach_blendR,
            ),
            PickupWaypoint(
                "Descending to pickup pose",
                list(motion_plan.pickup_pose),
                pickup_motion.descend_vel_percent,
                pickup_motion.descend_acc_percent,
                pickup_motion.descend_motion_type,
                pickup_motion.descend_blendR,
            ),
            PickupWaypoint(
                "Lifting from pickup pose",
                list(motion_plan.lift_pose),
                pickup_motion.lift_align_vel_percent,
                pickup_motion.lift_align_acc_percent,
                pickup_motion.lift_align_motion_type,
                pickup_motion.lift_align_blendR,
            ),
            PickupWaypoint(
                "Aligning workpiece to paint axis",
                list(motion_plan.align_pose),
                pickup_motion.lift_align_vel_percent,
                pickup_motion.lift_align_acc_percent,
                pickup_motion.lift_align_motion_type,
                pickup_motion.lift_align_blendR,
            ),
        ]

        if not combine_change_plane:
            waypoints.append(
                PickupWaypoint(
                    "Changing plane",
                    list(motion_plan.change_plane_pose),
                    pickup_motion.change_plane_vel_percent,
                    pickup_motion.change_plane_acc_percent,
                    pickup_motion.change_plane_motion_type,
                    pickup_motion.change_plane_blendR,
                )
            )

        safe_travel_waypoints = getattr(motion_plan, "safe_travel_waypoints", None) or [
            {
                "position": safe_travel_pose,
                "vel_percent": pickup_motion.stage_transition_vel_percent,
                "acc_percent": pickup_motion.stage_transition_acc_percent,
                "motion_type": pickup_motion.stage_transition_motion_type,
                "blendR": pickup_motion.stage_transition_blendR,
            }
            for safe_travel_pose in motion_plan.safe_travel_poses
        ]
        for waypoint_index, safe_travel_waypoint in enumerate(safe_travel_waypoints, start=1):
            waypoints.append(
                PickupWaypoint(
                    f"Safe travel waypoint {waypoint_index}",
                    list(safe_travel_waypoint["position"]),
                    float(safe_travel_waypoint["vel_percent"]),
                    float(safe_travel_waypoint["acc_percent"]),
                    str(safe_travel_waypoint.get("motion_type", "ptp")),
                    float(safe_travel_waypoint.get("blendR", 0.0)),
                )
            )

        for transition_index, transition_pose in enumerate(motion_plan.stage_transition_poses, start=1):
            waypoints.append(
                PickupWaypoint(
                    f"Stage transition {transition_index}",
                    owner._paint_contact_staging_command_pose(transition_pose, motion_plan.change_plane_pose),
                    pickup_motion.stage_transition_vel_percent,
                    pickup_motion.stage_transition_acc_percent,
                    pickup_motion.stage_transition_motion_type,
                    pickup_motion.stage_transition_blendR,
                )
            )

        staged_command_pose = owner._paint_contact_staging_command_pose(
            motion_plan.staged_pose,
            motion_plan.change_plane_pose,
        )
        staging_offset_pose = owner._paint_start_staging_offset_pose(staged_command_pose)
        staging_config = owner._paint_process_config().contact_staging
        _logger.info(
            "[PICKUP] staging offset before pivot contact: z_offset_mm=%.3f paint_axis=%s paint_axis_offset_mm=%.3f perpendicular_axis_offset_mm=%.3f direction=%s contact_pose=%s offset_pose=%s",
            staging_config.attach_z_offset_mm,
            owner._contact_motion_config.translation_axis,
            staging_config.attach_paint_axis_offset_mm,
            staging_config.attach_perpendicular_axis_offset_mm,
            owner._contact_motion_config.translation_direction,
            [round(float(v), 3) for v in staged_command_pose[:6]],
            [round(float(v), 3) for v in staging_offset_pose[:6]],
        )
        waypoints.append(
            PickupWaypoint(
                "Moving to staging offset before first pivot contact pose",
                staging_offset_pose,
                pickup_motion.first_contact_vel_percent,
                pickup_motion.first_contact_acc_percent,
                pickup_motion.first_contact_motion_type,
                pickup_motion.first_contact_blendR,
            )
        )

        return PickupPlan(
            strategy_name=self.name,
            motion_plan=motion_plan,
            waypoints=tuple(waypoints),
            vacuum_on_before_moves=True,
            change_plane_combined_with_first_contact=bool(combine_change_plane),
            contact_mode=normalize_pickup_contact_mode(pickup_motion.pickup_contact_mode),
            contact_waypoint_index=1,
            retract_reference_pose=(
                list(motion_plan.pickup_retract_reference_pose)
                if motion_plan.pickup_retract_reference_pose is not None
                else None
            ),
        )


class PaintPickupExecutor:
    """Execute the configured pickup strategy."""

    def __init__(self, owner, strategy: PaintPickupStrategy | None = None) -> None:
        self._owner = owner
        self._strategy = strategy or DefaultPickupStrategy()
        self._last_failure_message = ""

    def build_plan(self, prepared_workpiece: WorkpieceExecutionPlan) -> PickupPlan | None:
        return self._strategy.build_plan(self._owner, prepared_workpiece)

    @timed_step(_logger, "pickup_to_pivot")
    def execute(
        self,
        prepared_workpiece: WorkpieceExecutionPlan,
        *,
        pickup_plan: PickupPlan | None = None,
        prepared_continuation_segments: list[dict] | None = None,
    ) -> tuple[bool, str]:
        """Run pickup, align, and staging according to the configured strategy."""
        started = perf_counter()
        self._last_failure_message = ""
        _logger.info("[TIMING] pickup_to_pivot entered")
        if self._owner._robot_service is None:
            return False, "Robot service is not available"

        plan_started = perf_counter()
        if pickup_plan is None:
            with timed_block(_logger, "pickup_to_pivot_prepare", label="build_paint_pickup_plan"):
                pickup_plan = self.build_plan(prepared_workpiece)

        if pickup_plan is None:
            _logger.info("[TIMING] pickup_to_pivot success=false stage=build_poses total_elapsed_s=%.3f", elapsed_s(started))
            return False, (
                getattr(self._owner, "_last_pickup_plan_error", "")
                or getattr(self._owner, "_last_safe_travel_error", "")
                or "Could not compute pickup-to-pivot poses"
            )
        self._owner._last_pickup_plan = pickup_plan.motion_plan
        self._owner._last_pickup_contact_mode = pickup_plan.contact_mode
        _logger.info("[TIMING] pickup_to_pivot stage=build_poses elapsed_s=%.3f", elapsed_s(plan_started))

        if pickup_plan.contact_mode == PICKUP_CONTACT_MODE_SERVO_CONTACT:
            ok = self._execute_servo_contact_pickup_sequence(
                pickup_plan,
                prepared_continuation_segments=prepared_continuation_segments,
            )
        elif pickup_plan.contact_mode == PICKUP_CONTACT_MODE_HEIGHT_MEASURE:
            _logger.error("[PICKUP] Height-measured pickup Z mode is selected, but height service wiring is not implemented yet")
            return False, "Height-measured pickup Z mode is not wired yet"
        elif pickup_plan.contact_mode != PICKUP_CONTACT_MODE_PLANNED:
            _logger.error("[PICKUP] Invalid pickup contact mode: %s", pickup_plan.contact_mode)
            return False, f"Invalid pickup contact mode: {pickup_plan.contact_mode}"
        else:
            ok = self._execute_custom_pickup_sequence(pickup_plan)
        if ok:
            return True, "Pickup completed and robot is positioned before the first pivot contact pose"
        _logger.info("[TIMING] pickup_to_pivot success=false stage=ordered_pickup total_elapsed_s=%.3f", elapsed_s(started))
        detail = getattr(self._owner._motion, "last_motion_error", None)
        if self._last_failure_message:
            return False, self._last_failure_message
        if detail:
            return False, f"Ordered pickup sequence failed: {detail}"
        return False, "Ordered pickup sequence failed"

    def _execute_custom_pickup_sequence(self, pickup_plan: PickupPlan) -> bool:
        waypoints = list(pickup_plan.waypoints)
        if len(waypoints) < 2:
            return False
        if pickup_plan.change_plane_combined_with_first_contact:
            with timed_block(_logger, "pickup_phase", label="Changing plane combined with first pivot contact pose"):
                _logger.info(
                    "[PICKUP] Changing plane skipped as standalone move; orientation will be combined with first pivot contact pose"
                )
        if pickup_plan.vacuum_on_before_moves:
            ok, _msg = self._owner._motion.turn_vacuum_on()
            if not ok:
                return False

        if not self._move_waypoint_sequence(
            "Ordered pickup sequence",
            waypoints,
        ):
            return False
        return True

    def _execute_servo_contact_pickup_sequence(
        self,
        pickup_plan: PickupPlan,
        *,
        prepared_continuation_segments: list[dict] | None = None,
    ) -> bool:
        waypoints = list(pickup_plan.waypoints)
        contact_index = 1 if pickup_plan.contact_waypoint_index is None else int(pickup_plan.contact_waypoint_index)
        if contact_index <= 0 or contact_index >= len(waypoints):
            _logger.error("[PICKUP] Servo contact pickup has invalid contact waypoint index=%s", contact_index)
            return False

        pickup_motion = self._owner._paint_process_config().pickup_motion
        condition = getattr(self._owner, "_pickup_condition", None)
        if condition is None:
            _logger.error("[PICKUP] Servo contact pickup requested, but no pickup condition is configured")
            return False

        if pickup_plan.change_plane_combined_with_first_contact:
            with timed_block(_logger, "pickup_phase", label="Changing plane combined with first pivot contact pose"):
                _logger.info(
                    "[PICKUP] Changing plane skipped as standalone move; orientation will be combined with first pivot contact pose"
                )

        approach_waypoints = waypoints[:contact_index]
        remaining_waypoints = waypoints[contact_index + 1 :]
        retract_reference_pose = pickup_plan.retract_reference_pose
        if retract_reference_pose is None or len(retract_reference_pose) < 6:
            _logger.error("[PICKUP] Servo contact pickup has no valid calibration retract reference pose")
            return False
        predicted_retract_pose = list(waypoints[contact_index].pose)
        predicted_retract_pose[2] = float(retract_reference_pose[2])
        continuation_waypoints = remaining_waypoints[1:]
        motion_plane = str(
            getattr(getattr(self._owner, "_contact_motion_config", None), "motion_plane", "")
            or ""
        ).strip().lower()
        combine_lift_with_alignment = motion_plane == "xy_z_rz"
        combine_alignment_with_safe_travel = (
            len(continuation_waypoints) >= 2
            and continuation_waypoints[0].label == "Aligning workpiece to paint axis"
            and continuation_waypoints[1].label.startswith("Safe travel waypoint ")
        )
        if combine_alignment_with_safe_travel:
            align = continuation_waypoints[0]
            safe = continuation_waypoints[1]
            combined_safe_pose = list(safe.pose)
            combined_safe_pose[3:6] = list(align.pose[3:6])
            continuation_waypoints = [
                PickupWaypoint(
                    safe.label,
                    combined_safe_pose,
                    safe.vel_percent,
                    safe.acc_percent,
                    safe.motion_type,
                    safe.blendR,
                ),
                *continuation_waypoints[2:],
            ]
        if continuation_waypoints:
            first = continuation_waypoints[0]
            first_pose = list(first.pose)
            first_pose[2] = max(float(first_pose[2]), float(retract_reference_pose[2]))
            continuation_waypoints[0] = PickupWaypoint(
                first.label, first_pose, first.vel_percent, first.acc_percent,
                first.motion_type,
                # Safe-travel tuning belongs to the Paint Process settings.
                # Only synthetic/non-safe handoff moves retain the hard stop.
                first.blendR if first.label.startswith("Safe travel waypoint ") else 0.0,
            )
        if combine_lift_with_alignment or combine_alignment_with_safe_travel:
            # The retract has already established vertical clearance. When a
            # safe-travel waypoint exists, move there directly while applying
            # the alignment orientation; do not revisit the calibration XY.
            combined_waypoints = continuation_waypoints
        else:
            lift_waypoint = PickupWaypoint(
                "Raising workpiece after Servo retract",
                list(predicted_retract_pose),
                float(pickup_motion.lift_align_vel_percent),
                float(pickup_motion.lift_align_acc_percent),
                "ptp",
                10.0,
            )
            combined_waypoints = [lift_waypoint] + continuation_waypoints
        combined_segments = build_paint_pickup_segments(combined_waypoints)
        combined_segments.extend(prepared_continuation_segments or [])
        prepared_plan_id: str | None = None
        prepare = getattr(self._owner._robot_service, "prepare_ordered_motion_chain", None)
        if combined_segments and callable(prepare):
            try:
                prepared = prepare(
                    segments=combined_segments,
                    start_position=predicted_retract_pose,
                    tool=int(self._owner._pickup_tool),
                    user=int(self._owner._pickup_user),
                    allow_servo_during_prepare=True,
                )
                if isinstance(prepared, dict) and prepared.get("plan_id"):
                    prepared_plan_id = str(prepared["plan_id"])
            except Exception:
                _logger.exception("[PICKUP] Failed to prepare continuation before Servo pickup")

        def discard_prepared() -> None:
            if not prepared_plan_id:
                return
            discard = getattr(self._owner._robot_service, "discard_prepared_ordered_motion_chain", None)
            if callable(discard):
                try:
                    discard(prepared_plan_id)
                except Exception:
                    _logger.exception("[PICKUP] Failed to discard prepared continuation plan_id=%s", prepared_plan_id)

        if pickup_plan.vacuum_on_before_moves:
            ok, _msg = self._owner._motion.turn_vacuum_on(required=True)
            if not ok:
                discard_prepared()
                return False

        if not self._move_waypoint_sequence("Pickup approach before servo contact", approach_waypoints):
            discard_prepared()
            return False

        contact_speed_mm_s = float(pickup_motion.servo_contact_linear_mm_s)
        minimum_contact_z_mm = float(getattr(pickup_motion, "servo_contact_min_z_mm", 0.0))
        _logger.info(
            "[PICKUP] Servo contact descent starting: speed_mm_s=%.3f timeout_s=%.3f tool=%d user=%d",
            contact_speed_mm_s,
            float(pickup_motion.servo_contact_timeout_s),
            int(self._owner._pickup_tool),
            int(self._owner._pickup_user),
        )
        procedure = ServoUntilConditionProcedure(self._owner._robot_service, condition)
        control = getattr(self._owner, "_active_execution_control", None)
        result = procedure.run(
            config=ServoUntilConditionConfig(
                axis=RobotAxis.Z,
                direction=Direction.MINUS,
                linear_mm_s=contact_speed_mm_s,
                frame="user",
                tool=int(self._owner._pickup_tool),
                user=int(self._owner._pickup_user),
                poll_interval_s=float(pickup_motion.servo_contact_poll_interval_s),
                timeout_s=float(pickup_motion.servo_contact_timeout_s),
                preflight_condition_read_attempts=int(pickup_motion.servo_contact_preflight_read_attempts),
                condition_read_failure_limit=int(pickup_motion.servo_contact_read_failure_limit),
                allow_subzero_descent=True,
                disable_collision_checking=True,
                minimum_z_mm=minimum_contact_z_mm,
            ),
            retract=ServoRetractConfig(
                target_pose=predicted_retract_pose,
                motion_type="fast_lin",
                linear_mm_s=float(getattr(pickup_motion, "servo_contact_retract_linear_mm_s", 25.0)),
                final_linear_mm_s=float(
                    getattr(pickup_motion, "servo_contact_retract_final_linear_mm_s", 50.0)
                ),
                slowdown_distance_mm=float(
                    getattr(pickup_motion, "servo_contact_retract_slowdown_clearance_mm", 20.0)
                ),
                poll_interval_s=float(pickup_motion.servo_contact_poll_interval_s),
                timeout_s=3.0,
                position_tolerance_mm=2.0,
                safety_margin_mm=float(
                    getattr(pickup_motion, "servo_contact_retract_safety_margin_mm", 10.0)
                ),
                fast_lin_velocity_percent=float(pickup_motion.lift_align_vel_percent),
                fast_lin_acceleration_percent=float(pickup_motion.lift_align_acc_percent),
            ),
            cancel_requested=(
                None
                if control is None
                else lambda: bool(control.should_stop() or control.pause_requested())
            ),
        )
        _logger.info(
            "[PICKUP] Servo contact descent result success=%s detected=%s timeout=%s elapsed_s=%.3f message=%s",
            result.success,
            result.detected,
            result.timed_out,
            result.elapsed_s,
            result.message,
        )
        if not result.success:
            discard_prepared()
            if result.timed_out or result.message == "timeout":
                off_ok, off_msg = self._owner._motion.turn_vacuum_off()
                if not off_ok:
                    _logger.error(
                        "[PICKUP] Vacuum pump OFF failed after servo-contact timeout: %s",
                        off_msg,
                    )
                recovery_waypoint = PickupWaypoint(
                    "Returning to calibration pickup origin after no contact",
                    list(approach_waypoints[-1].pose),
                    float(approach_waypoints[-1].vel_percent),
                    float(approach_waypoints[-1].acc_percent),
                    "linear",
                    0.0,
                )
                current_pose = self._read_fresh_pose()
                if pickup_pose_is_close(current_pose, recovery_waypoint.pose):
                    _logger.info(
                        "[PICKUP] Calibration timeout recovery skipped: robot already at pickup origin"
                    )
                    recovered = True
                else:
                    recovered = self._move_waypoint_sequence(
                        "Calibration pickup timeout recovery",
                        [recovery_waypoint],
                    )
                recovery_failures = []
                if not off_ok:
                    recovery_failures.append(f"vacuum pump OFF failed: {off_msg}")
                if not recovered:
                    recovery_failures.append("return to pickup origin failed")
                self._last_failure_message = (
                    "Calibration servo pickup timed out; " + "; ".join(recovery_failures)
                    if recovery_failures
                    else NO_WORKPIECE_AT_CALIBRATION
                )
            return False
        if not pickup_condition_is_active_after_retract(condition):
            discard_prepared()
            off_ok, off_msg = self._owner._motion.turn_vacuum_off()
            if not off_ok:
                self._last_failure_message = (
                    "Workpiece is no longer detected after Servo retract; "
                    f"vacuum pump OFF also failed: {off_msg}"
                )
            return False
        current_pose = self._wait_for_stable_pose()
        if current_pose is None:
            discard_prepared()
            _logger.error("[PICKUP] Current pose unavailable after servo contact")
            return False
        retract_z_error = abs(float(predicted_retract_pose[2]) - float(current_pose[2]))
        if retract_z_error > 2.0:
            discard_prepared()
            _logger.error(
                "[PICKUP] Servo retract did not reach calibration target Z "
                "target_z=%.3f current_z=%.3f error_mm=%.3f",
                float(predicted_retract_pose[2]),
                float(current_pose[2]),
                retract_z_error,
            )
            return False

        if not combined_segments:
            return True
        if prepared_plan_id:
            execution = self._owner._robot_service.execute_prepared_ordered_motion_chain(prepared_plan_id)
            ok = bool(
                isinstance(execution, dict)
                and execution.get("state") == "completed"
                and execution.get("result") == 0
            )
            if not ok:
                discard_prepared()
        else:
            ok = self._owner._motion.move_ordered_pickup_sequence(
                "Pickup lift and continuation after completed Servo retract",
                combined_segments,
            )
        return bool(ok)

    def _read_fresh_pose(self) -> list[float] | None:
        getter = getattr(self._owner._robot_service, "get_current_position_fresh", None)
        if not callable(getter):
            getter = getattr(self._owner._robot_service, "get_current_position", None)
        if not callable(getter):
            return None
        try:
            pose = getter()
        except Exception:
            _logger.exception("[PICKUP] Failed to read current pose after servo contact")
            return None
        if pose is None or len(pose) < 6:
            return None
        return [float(value) for value in pose[:6]]

    def _wait_for_stable_pose(self, timeout_s: float = 1.0) -> list[float] | None:
        deadline = time.monotonic() + timeout_s
        previous = None
        stable = 0
        while time.monotonic() < deadline:
            pose = self._read_fresh_pose()
            if pose is not None and previous is not None:
                xyz_delta = math.sqrt(sum((pose[i] - previous[i]) ** 2 for i in range(3)))
                angular_delta = max(
                    abs((pose[i] - previous[i] + 180.0) % 360.0 - 180.0)
                    for i in range(3, 6)
                )
                stable = stable + 1 if xyz_delta <= 0.5 and angular_delta <= 0.2 else 0
                if stable >= 3:
                    return pose
            else:
                stable = 0
            previous = pose
            time.sleep(0.05)
        _logger.error("[PICKUP] Post-retract pose stability timeout")
        return None

    def _move_waypoint_sequence(self, label: str, waypoints: list[PickupWaypoint]) -> bool:
        segments = build_paint_pickup_segments(waypoints)
        _logger.info(
            "[PICKUP] Executing custom pickup sequence labels=%s vel_acc=%s",
            " -> ".join(waypoint.label for waypoint in waypoints),
            [
                (round(float(segment["vel"]), 3), round(float(segment["acc"]), 3))
                for segment in segments
            ],
        )
        return bool(self._owner._motion.move_ordered_pickup_sequence(label, segments))

    @staticmethod
    def _failure_message_for(label: str) -> str:
        messages = {
            "Moving to pickup approach pose": "Pickup approach move failed",
            "Descending to pickup pose": "Pickup descend move failed",
            "Lifting from pickup pose": "Pickup succeeded, but lift move failed",
            "Aligning workpiece to paint axis": "Pickup succeeded, but align move failed",
            "Changing plane": "Pickup succeeded, but change-plane move failed",
            "Moving to staging offset before first pivot contact pose": "Pickup succeeded, but move to staging offset failed",
        }
        if label in messages:
            return messages[label]
        if label.startswith("Stage transition "):
            return f"Pickup succeeded, but {label.lower()} failed"
        return f"Pickup succeeded, but {label} failed"


def build_ordered_pickup_segments(pickup_plan: PickupPlan) -> list[dict]:
    """
    Build ordered paint pickup/staging motion segments from a pickup plan.

    Prefer `build_paint_pickup_segments(...)` when the caller already has the
    waypoint list.
    """
    return build_paint_pickup_segments(pickup_plan.waypoints)


def build_paint_pickup_segments(waypoints: tuple[PickupWaypoint, ...] | list[PickupWaypoint]) -> list[dict]:
    """
    Build paint pickup/staging motion segments.

    This is the place to adjust pickup ordered-chain move shape:

    - pickup segment `type`
    - pickup/staging velocity and acceleration propagation
    - pickup route `blendR`
    - which waypoints must stop before continuing
    """
    segments: list[dict] = []
    for waypoint_index, waypoint in enumerate(waypoints):
        is_last_pickup_waypoint = waypoint_index == len(waypoints) - 1
        is_pickup_contact = waypoint.label == "Descending to pickup pose"
        move_type = "linear" if is_pickup_contact else "ptp"
        configured_type = str(getattr(waypoint, "motion_type", None) or "").strip().lower()
        if configured_type in {"ptp", "linear"}:
            move_type = configured_type
        default_blend_r = (
            0.0
            if (
                is_last_pickup_waypoint
                or is_pickup_contact
            )
            else 20.0
        )
        configured_blend_r = getattr(waypoint, "blendR", None)
        blend_r = default_blend_r if configured_blend_r is None else float(configured_blend_r)
        if is_last_pickup_waypoint:
            blend_r = 0.0
        segment = {
            "type": move_type,
            "label": waypoint.label,
            "position": list(waypoint.pose),
            "vel": float(waypoint.vel_percent),
            "acc": float(waypoint.acc_percent),
            "blendR": max(0.0, blend_r),
        }
        if segments and _equivalent_pickup_poses(segments[-1]["position"], segment["position"]):
            _logger.info(
                "[PICKUP] Removing redundant no-op waypoint %r at the same pose as %r",
                segment["label"],
                segments[-1]["label"],
            )
            segments[-1]["blendR"] = segment["blendR"]
            continue
        segments.append(segment)
    return segments


def _equivalent_pickup_poses(first: list[float], second: list[float]) -> bool:
    if len(first) < 6 or len(second) < 6:
        return False
    if any(abs(float(first[index]) - float(second[index])) > 1e-3 for index in range(3)):
        return False
    for index in range(3, 6):
        delta = (float(first[index]) - float(second[index]) + 180.0) % 360.0 - 180.0
        if abs(delta) > 1e-3:
            return False
    return True


def build_ordered_paint_contact_segments(
    paint_paths: list[list[list[float]]],
    paint_jobs: list[dict],
    contact_staging,
) -> list[dict]:
    """
    Build ordered paint-contact path segments.

    This is the place to adjust ordered paint-contact path command shape.
    """
    segments: list[dict] = []
    for path_index, command_path in enumerate(paint_paths):
        if not command_path:
            continue
        job = paint_jobs[path_index] if path_index < len(paint_jobs) else {}
        readiness_group = f"paint_contact_{path_index + 1}"
        segments.append(
            {
                "type": "linear",
                "label": f"paint_attach_{path_index + 1}",
                "position": list(command_path[0]),
                "vel": float(contact_staging.attach_vel_percent),
                "acc": float(contact_staging.attach_acc_percent),
                "blendR": 0.0,
                "protected": True,
                "readiness_group": readiness_group,
                "execution_group": readiness_group,
                "execution_policy": "concatenate",
            }
        )
        segments.append(
            {
                "type": "path",
                "label": f"paint_contact_{path_index + 1}:{job.get('pattern_type', 'Path')}",
                "path": command_path,
                "vel": float(job.get("vel", 10.0)),
                "acc": float(job.get("acc", 30.0)),
                "protected": True,
                "limit_profile": "paint_contact",
                "readiness_group": readiness_group,
                "execution_group": readiness_group,
                "execution_policy": "concatenate",
            }
        )
    return segments


def build_magazine_pickup_release_segments(
    transfer_waypoints: tuple[tuple, ...],
) -> list[dict]:
    """
    Build ordered magazine pickup-to-release segments.

    This is the place to adjust magazine transfer `blendR`.
    """
    segments: list[dict] = []
    for index, waypoint in enumerate(transfer_waypoints):
        label, pose, velocity, acceleration, move_type = waypoint[:5]
        blend_r = float(waypoint[5]) if len(waypoint) >= 6 else 0.0
        if len(waypoint) < 6 and label == "Lifting magazine workpiece" and index + 1 < len(transfer_waypoints):
            blend_r = 20.0
        if index == len(transfer_waypoints) - 1:
            blend_r = 0.0
        segments.append(
            {
                "type": move_type,
                "label": label,
                "position": list(pose),
                "vel": float(velocity),
                "acc": float(acceleration),
                "blendR": blend_r,
            }
        )
    return segments

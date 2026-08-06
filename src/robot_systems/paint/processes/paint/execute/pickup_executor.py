from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.timing import timed_block, timed_step

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PickupWaypoint:
    """One carried-part pickup or staging move."""

    label: str
    pose: list[float]
    vel_percent: float
    acc_percent: float


@dataclass(frozen=True)
class PickupPlan:
    """Resolved pickup sequence for moving the workpiece to the paint start."""

    strategy_name: str
    motion_plan: object
    waypoints: tuple[PickupWaypoint, ...]
    vacuum_on_before_moves: bool = True
    change_plane_combined_with_first_contact: bool = False


class PaintPickupStrategy(Protocol):
    """Build pickup/staging plans without exposing strategy details to the main executor."""

    name: str

    def build_plan(self, owner, prepared_workpiece: WorkpieceExecutionPlan) -> PickupPlan | None:
        """Return the ordered pickup actions for the active workpiece."""


class DefaultPickupStrategy:
    """Default strategy: reproduce the existing pickup, align, and pivot-staging sequence."""

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
            ),
            PickupWaypoint(
                "Descending to pickup pose",
                list(motion_plan.pickup_pose),
                pickup_motion.descend_vel_percent,
                pickup_motion.descend_acc_percent,
            ),
            PickupWaypoint(
                "Lifting from pickup pose",
                list(motion_plan.lift_pose),
                pickup_motion.lift_align_vel_percent,
                pickup_motion.lift_align_acc_percent,
            ),
            PickupWaypoint(
                "Aligning workpiece to paint axis",
                list(motion_plan.align_pose),
                pickup_motion.lift_align_vel_percent,
                pickup_motion.lift_align_acc_percent,
            ),
        ]

        if not combine_change_plane:
            waypoints.append(
                PickupWaypoint(
                    "Changing plane",
                    list(motion_plan.change_plane_pose),
                    pickup_motion.change_plane_vel_percent,
                    pickup_motion.change_plane_acc_percent,
                )
            )

        safe_travel_waypoints = getattr(motion_plan, "safe_travel_waypoints", None) or [
            {
                "position": safe_travel_pose,
                "vel_percent": pickup_motion.stage_transition_vel_percent,
                "acc_percent": pickup_motion.stage_transition_acc_percent,
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
                )
            )

        for transition_index, transition_pose in enumerate(motion_plan.stage_transition_poses, start=1):
            waypoints.append(
                PickupWaypoint(
                    f"Stage transition {transition_index}",
                    owner._paint_contact_staging_command_pose(transition_pose, motion_plan.change_plane_pose),
                    pickup_motion.stage_transition_vel_percent,
                    pickup_motion.stage_transition_acc_percent,
                )
            )

        staged_command_pose = owner._paint_contact_staging_command_pose(
            motion_plan.staged_pose,
            motion_plan.change_plane_pose,
        )
        staging_offset_pose = owner._paint_start_staging_offset_pose(staged_command_pose)
        _logger.info(
            "[PICKUP] staging offset before pivot contact: z_offset_mm=%.3f paint_axis=%s paint_axis_offset_mm=%.3f direction=%s contact_pose=%s offset_pose=%s",
            owner._staging_z_offset_mm,
            owner._contact_motion_config.translation_axis,
            owner._staging_paint_axis_offset_mm,
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
            )
        )

        return PickupPlan(
            strategy_name=self.name,
            motion_plan=motion_plan,
            waypoints=tuple(waypoints),
            vacuum_on_before_moves=True,
            change_plane_combined_with_first_contact=bool(combine_change_plane),
        )


class PaintPickupExecutor:
    """Execute the configured pickup strategy."""

    def __init__(self, owner, strategy: PaintPickupStrategy | None = None) -> None:
        self._owner = owner
        self._strategy = strategy or DefaultPickupStrategy()

    def build_plan(self, prepared_workpiece: WorkpieceExecutionPlan) -> PickupPlan | None:
        return self._strategy.build_plan(self._owner, prepared_workpiece)

    @timed_step(_logger, "pickup_to_pivot")
    def execute(self, prepared_workpiece: WorkpieceExecutionPlan) -> tuple[bool, str]:
        """Run pickup, align, and staging according to the configured strategy."""
        started = perf_counter()
        _logger.info("[TIMING] pickup_to_pivot entered")
        if self._owner._robot_service is None:
            return False, "Robot service is not available"

        plan_started = perf_counter()
        with timed_block(_logger, "pickup_to_pivot_prepare", label="build_pickup_transfer_plan"):
            pickup_plan = self.build_plan(prepared_workpiece)

        if pickup_plan is None:
            _logger.info("[TIMING] pickup_to_pivot success=false stage=build_poses total_elapsed_s=%.3f", elapsed_s(started))
            return False, getattr(self._owner, "_last_safe_travel_error", "") or "Could not compute pickup-to-pivot poses"
        self._owner._last_pickup_plan = pickup_plan.motion_plan
        _logger.info("[TIMING] pickup_to_pivot stage=build_poses elapsed_s=%.3f", elapsed_s(plan_started))

        insert_calibration_return = self._owner._should_return_to_calibration_between_xy_rz_pickup_and_pivot()
        if not insert_calibration_return and self._execute_custom_pickup_sequence(pickup_plan):
            return True, "Pickup completed and robot is positioned before the first pivot contact pose"
        if not insert_calibration_return:
            _logger.info("[TIMING] pickup_to_pivot success=false stage=ordered_pickup total_elapsed_s=%.3f", elapsed_s(started))
            return False, "Ordered pickup sequence failed"

        if insert_calibration_return:
            _logger.info("[PICKUP] XY/RZ pickup will return to calibration after alignment before pivot staging")
        if pickup_plan.vacuum_on_before_moves:
            ok, msg = self._owner._turn_vacuum_on()
            if not ok:
                _logger.info("[TIMING] pickup_to_pivot success=false stage=vacuum_on total_elapsed_s=%.3f", elapsed_s(started))
                return False, msg

        for waypoint in pickup_plan.waypoints:
            if (
                pickup_plan.change_plane_combined_with_first_contact
                and waypoint.label == "Moving to staging offset before first pivot contact pose"
            ):
                with timed_block(_logger, "pickup_phase", label="Changing plane combined with first pivot contact pose"):
                    _logger.info(
                        "[PICKUP] Changing plane skipped as standalone move; orientation will be combined with first pivot contact pose"
                    )

            if not self._owner._move_pickup_phase(
                waypoint.label,
                list(waypoint.pose),
                velocity=waypoint.vel_percent,
                acceleration=waypoint.acc_percent,
            ):
                _logger.info(
                    "[TIMING] pickup_to_pivot success=false stage=%s total_elapsed_s=%.3f",
                    waypoint.label,
                    elapsed_s(started),
                )
                return False, self._failure_message_for(waypoint.label)
            if waypoint.label == "Aligning workpiece to paint axis":
                ok, msg = self._owner._return_to_calibration_before_xy_rz_pivot()
                if not ok:
                    _logger.info(
                        "[TIMING] pickup_to_pivot success=false stage=return_to_calibration_after_align total_elapsed_s=%.3f",
                        elapsed_s(started),
                    )
                    return False, msg

        return True, "Pickup completed and robot is positioned before the first pivot contact pose"

    def _execute_custom_pickup_sequence(self, pickup_plan: PickupPlan) -> bool:
        waypoints = list(pickup_plan.waypoints)
        if len(waypoints) < 2:
            return False
        if pickup_plan.change_plane_combined_with_first_contact:
            with timed_block(_logger, "pickup_phase", label="Changing plane combined with first pivot contact pose"):
                _logger.info(
                    "[PICKUP] Changing plane skipped as standalone move; orientation will be combined with first pivot contact pose"
                )
        move_sequence = getattr(self._owner, "_move_ordered_pickup_sequence", None)
        if not callable(move_sequence):
            return False

        if pickup_plan.vacuum_on_before_moves:
            ok, _msg = self._owner._turn_vacuum_on()
            if not ok:
                return False

        if not self._move_waypoint_sequence(
            move_sequence,
            "Ordered pickup sequence",
            waypoints,
        ):
            return False
        return True

    def _move_waypoint_sequence(self, move_sequence, label: str, waypoints: list[PickupWaypoint]) -> bool:
        segments = [
            {
                "type": "linear",
                "label": waypoint.label,
                "position": list(waypoint.pose),
                "vel": float(waypoint.vel_percent),
                "acc": float(waypoint.acc_percent),
            }
            for waypoint in waypoints
        ]
        _logger.info(
            "[PICKUP] Executing custom pickup sequence labels=%s vel_acc=%s",
            " -> ".join(waypoint.label for waypoint in waypoints),
            [
                (round(float(segment["vel"]), 3), round(float(segment["acc"]), 3))
                for segment in segments
            ],
        )
        return bool(move_sequence(label, segments))

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

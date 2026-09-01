from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from src.engine.geometry.planar import unwrap_degrees
from src.robot_systems.paint.processes.paint.config import PAINT_PROCESS_CONFIG
from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.motion_handlers import (
    motion_failure_message,
)
from src.robot_systems.paint.timing import timed_step

_logger = logging.getLogger(__name__)

_PLATE_LAYOUT_CORRIDOR_PADDING_MM = 10.0


@dataclass(frozen=True)
class DropoffReleaseWaypoint:
    """One release-strategy move or release action."""

    label: str
    pose: list[float] | None
    vel_percent: float
    acc_percent: float
    motion_type: str = "ptp"
    blendR: float = 0.0
    release_here: bool = False
    corridor_id: str | None = None


@dataclass(frozen=True)
class DropoffReleasePlan:
    """Resolved release sequence for the currently held painted workpiece."""

    strategy_name: str
    waypoints: tuple[DropoffReleaseWaypoint, ...]


def open_dropoff_passage_for_preparation(executor: object) -> tuple[bool, str]:
    """Open the configured passage before planning any route that crosses its lid."""
    if _dropoff_strategy_name(executor) == "plate_layout":
        return True, ""
    # Validate the configured release target before changing the planning scene.
    # A disabled sub-zero dropoff must not open the paint passage or allow an
    # ordered cleanup chain containing that target to execute.
    if _dropoff_strategy_name(executor) == "movement_group":
        dropoff = executor._paint_process_config().dropoff
        pose = _resolve_dropoff_align_pose(executor)
        if pose is not None and float(pose[2]) < 0.0 and not bool(
            getattr(dropoff, "allow_sub_zero_dropoff", False)
        ):
            _logger.error(
                "[DROPOFF] Refusing preparation before opening passage: "
                "negative target with Allow Sub-Zero Dropoff disabled"
            )
            return False, "Dropoff cancelled: Allow Sub-Zero Dropoff is disabled"
    passage_id = str(getattr(executor, "_dropoff_motion_corridor_id", "") or "")
    if not passage_id:
        return True, ""
    setter = getattr(executor._robot_service, "set_motion_passage_closed", None)
    if not callable(setter):
        return False, f"Dropoff preparation cancelled: passage control is unavailable for '{passage_id}'"
    if not setter(passage_id, False):
        return False, f"Dropoff preparation cancelled: failed to open passage '{passage_id}'"
    _logger.info("[DROPOFF] Opened motion passage '%s' before dropoff-route planning", passage_id)
    return True, ""


@timed_step(_logger, "prepare_dropoff_unwind")
def execute_dropoff_preparation_for_executor(executor: object) -> tuple[bool, str]:
    """Build and execute paint-to-dropoff safe travel, align, and Joint 6 unwind."""
    dryer_ready = (
        None
        if _dropoff_strategy_name(executor) == "plate_layout"
        else getattr(executor, "_dryer_ready_for_release", None)
    )
    if callable(dryer_ready):
        try:
            ready, reason = dryer_ready()
        except Exception:
            _logger.exception("[DROPOFF] Failed to verify dryer readiness before dropoff")
            return False, "Dropoff cancelled: dryer readiness could not be verified"
        if not ready:
            detail = str(reason or "the previous dryer sequence failed")
            return False, f"Dropoff cancelled: {detail}"

    if executor._dropoff_unwind_prepared:
        _logger.info("[DROPOFF] Pre-dropoff align/unwind already completed by ordered cleanup chain")
        return True, ""

    if _dropoff_strategy_name(executor) == "plate_layout":
        return _execute_plate_layout_preparation(executor)

    if _should_prepare_dropoff_align_before_unwind(executor):
        opened, message = open_dropoff_passage_for_preparation(executor)
        if not opened:
            return False, message

    if getattr(executor, "_last_pickup_contact_mode", None) == "sensor_controlled_fast_lin":
        segments, final_pose = build_ordered_dropoff_preparation_segments(executor)
        if not segments:
            return False, "Pivot paint finished, but ordered dropoff preparation could not be built"
        _logger.info(
            "[DROPOFF] Executing servo-contact dropoff preparation as one ordered chain segments=%d blendR=%s",
            len(segments),
            [segment.get("blendR") for segment in segments],
        )
        if not executor._motion.move_ordered_pickup_sequence(
            "Servo-contact ordered dropoff preparation",
            segments,
        ):
            return False, "Pivot paint finished, but ordered dropoff preparation failed"
        executor._dropoff_unwind_prepared = True
        if final_pose is not None:
            executor._last_process_end_pose = list(final_pose)
        return True, ""

    config = executor._paint_process_config()
    safe_waypoints = _resolve_dropoff_safe_travel_waypoints(executor)
    if bool(config.dropoff_safe_travel.enabled):
        if not safe_waypoints:
            return False, "Pivot paint finished, but paint-to-dropoff safe travel waypoints are not configured"
        for index, safe_waypoint in enumerate(safe_waypoints, start=1):
            if not executor._motion.move_pickup_phase(
                f"Moving through paint-to-dropoff safe travel waypoint {index}",
                safe_waypoint["position"],
                velocity=float(safe_waypoint["vel_percent"]),
                acceleration=float(safe_waypoint["acc_percent"]),
                motion_type=str(safe_waypoint.get("motion_type", "ptp")),
                blendR=float(safe_waypoint.get("blendR", 0.0)),
            ):
                return False, "Pivot paint finished, but paint-to-dropoff safe travel move failed"

    if _should_prepare_dropoff_align_before_unwind(executor):
        align_pose = _resolve_dropoff_preparation_pose(executor)
        if align_pose is None:
            return False, "Pivot paint finished, but no dropoff pose is available for safe pre-dropoff unwind alignment"
        if not executor._motion.move_pickup_phase(
            "Moving to dropoff pose before unwind",
            align_pose,
            velocity=config.dropoff.release_align_vel_percent,
            acceleration=config.dropoff.release_align_acc_percent,
            motion_type=config.dropoff.release_align_motion_type,
            blendR=float(config.dropoff.release_align_blendR),
        ):
            return False, "Pivot paint finished, but move to dropoff pose failed before unwind"
    elif executor._configured_contact_motion_plane == "xz_y_ry":
        return False, "Pivot paint finished, but no dropoff pose is available for safe pre-dropoff unwind alignment"

    if executor._robot_service is None:
        return False, "Pivot paint finished, but robot service is not available for pre-dropoff Joint 6 unwind"

    _logger.info(
        "[DROPOFF] Unwinding Joint 6 before dropoff strategy vel=%.1f acc=%.1f queue_if_busy=%s",
        config.navigation_return.unwind_vel_percent,
        config.navigation_return.unwind_acc_percent,
        PAINT_PROCESS_CONFIG.navigation_return.unwind_queue_if_busy,
    )
    ok = executor._robot_service.unwind_joint6(
        blocking=True,
        queue_if_busy=PAINT_PROCESS_CONFIG.navigation_return.unwind_queue_if_busy,
        vel=config.navigation_return.unwind_vel_percent,
        acc=config.navigation_return.unwind_acc_percent,
    )
    if not ok:
        return False, "Pivot paint finished, but Joint 6 unwind failed before dropoff"
    return True, ""


@timed_step(_logger, "pre_release_dropoff")
def execute_dropoff_release_for_executor(
    executor: object,
    *,
    next_cycle_start: dict | None = None,
) -> tuple[bool, str]:
    """Build and execute the configured dropoff release strategy."""
    started = perf_counter()
    plan = _build_dropoff_release_plan(executor)
    executor._last_prepositioned_start_group = None
    release_count = sum(1 for waypoint in plan.waypoints if waypoint.release_here)
    if release_count != 1:
        if plan.strategy_name == "movement_group":
            return False, "Dropoff movement group 'Dropoff' is not configured"
        return False, f"Dropoff strategy '{plan.strategy_name}' must define exactly one release waypoint"

    _logger.info(
        "[DROPOFF] executing strategy=%s waypoints=%d",
        plan.strategy_name,
        len(plan.waypoints),
    )
    release_index, release_waypoint = next(
        (index, waypoint)
        for index, waypoint in enumerate(plan.waypoints, start=1)
        if waypoint.release_here
    )
    ordered_release_pose_completed = (
        bool(getattr(executor, "_dropoff_unwind_prepared", False))
        and release_waypoint.pose is not None
        and _poses_close(release_waypoint.pose, getattr(executor, "_last_process_end_pose", None))
    )
    release_completed = False
    for index, waypoint in enumerate(plan.waypoints, start=1):
        waypoint_started = perf_counter()
        if waypoint.pose is not None:
            already_at_release_pose = ordered_release_pose_completed and waypoint.release_here
            superseded_approach = ordered_release_pose_completed and index < release_index
            if already_at_release_pose:
                _logger.info(
                    "[DROPOFF] waypoint '%s' already completed by ordered cleanup chain; releasing in place",
                    waypoint.label,
                )
            elif superseded_approach:
                _logger.info(
                    "[DROPOFF] waypoint '%s' superseded by ordered descent to release pose",
                    waypoint.label,
                )
            elif not executor._motion.move_pickup_phase(
                waypoint.label,
                list(waypoint.pose),
                velocity=waypoint.vel_percent,
                acceleration=waypoint.acc_percent,
                motion_type="linear" if waypoint.corridor_id else waypoint.motion_type,
                blendR=waypoint.blendR,
                corridor_id=waypoint.corridor_id,
            ):
                _logger.info(
                    "[TIMING] pre_release_dropoff success=false strategy=%s waypoint=%d label=%s elapsed_s=%.3f total_elapsed_s=%.3f",
                    plan.strategy_name,
                    index,
                    waypoint.label,
                    elapsed_s(waypoint_started),
                    elapsed_s(started),
                )
                failure = (
                    f"Workpiece release completed, but post-release dropoff waypoint "
                    f"'{waypoint.label}' failed; robot may still be inside the dropoff passage"
                    if release_completed
                    else f"Pivot paint finished, but dropoff waypoint '{waypoint.label}' failed before release"
                )
                return False, motion_failure_message(executor._robot_service, failure)

        if waypoint.release_here:
            ok, msg = executor._motion.turn_vacuum_off()
            if not ok:
                _logger.info(
                    "[TIMING] pre_release_dropoff success=false strategy=%s waypoint=%d stage=release elapsed_s=%.3f total_elapsed_s=%.3f",
                    plan.strategy_name,
                    index,
                    elapsed_s(waypoint_started),
                    elapsed_s(started),
                )
                return False, msg
            ok, msg = _verify_workpiece_released(executor)
            if not ok:
                _logger.info(
                    "[TIMING] pre_release_dropoff success=false strategy=%s waypoint=%d stage=release_verification elapsed_s=%.3f total_elapsed_s=%.3f",
                    plan.strategy_name,
                    index,
                    elapsed_s(waypoint_started),
                    elapsed_s(started),
                )
                return False, msg
            release_completed = True
            ok, msg = _on_workpiece_release_verified(executor)
            if not ok:
                _logger.info(
                    "[TIMING] pre_release_dropoff success=false strategy=%s waypoint=%d "
                    "stage=release_verified_callback elapsed_s=%.3f total_elapsed_s=%.3f",
                    plan.strategy_name,
                    index,
                    elapsed_s(waypoint_started),
                    elapsed_s(started),
                )
                return False, msg

    if next_cycle_start is not None:
        if not _move_to_next_cycle_start(executor, next_cycle_start):
            return False, "Dropoff retracted safely, but move to next-cycle start failed"
        if not _next_cycle_start_pose_reached(executor, next_cycle_start):
            return False, "Dropoff retracted safely, but next-cycle start pose was not reached"
        executor._last_prepositioned_start_group = str(next_cycle_start["group_id"])
        _logger.info(
            "[NEXT_CYCLE] Reached start group='%s'",
            executor._last_prepositioned_start_group,
        )

    _logger.info(
        "[DROPOFF] strategy=%s completed elapsed_s=%.3f",
        plan.strategy_name,
        elapsed_s(started),
    )
    return True, ""


def _move_to_next_cycle_start(executor: object, next_cycle_start: dict) -> bool:
    return bool(executor._motion.move_pickup_phase(
        f"Moving to next-cycle start '{next_cycle_start['group_id']}'",
        list(next_cycle_start["position"]),
        velocity=float(next_cycle_start["vel"]),
        acceleration=float(next_cycle_start["acc"]),
        motion_type=str(next_cycle_start.get("type", "ptp")),
        blendR=0.0,
    ))


def _next_cycle_start_pose_reached(
    executor: object,
    next_cycle_start: dict,
    position_tolerance_mm: float = 2.0,
    orientation_tolerance_deg: float = 2.0,
) -> bool:
    getter = getattr(executor._robot_service, "get_current_position_fresh", None)
    if not callable(getter):
        getter = getattr(executor._robot_service, "get_current_position", None)
    if not callable(getter):
        return False
    try:
        actual = getter()
    except Exception:
        _logger.exception("[NEXT_CYCLE] Failed to read pose after start move")
        return False
    expected = next_cycle_start.get("position")
    if not isinstance(actual, (list, tuple)) or not isinstance(expected, (list, tuple)):
        return False
    if len(actual) < 6 or len(expected) < 6:
        return False
    position_error = float(np.linalg.norm(
        np.asarray(actual[:3], dtype=float) - np.asarray(expected[:3], dtype=float)
    ))
    orientation_error = max(
        abs((float(actual[index]) - float(expected[index]) + 180.0) % 360.0 - 180.0)
        for index in range(3, 6)
    )
    reached = (
        position_error <= float(position_tolerance_mm)
        and orientation_error <= float(orientation_tolerance_deg)
    )
    _logger.info(
        "[NEXT_CYCLE] Start-pose verification reached=%s position_error_mm=%.3f "
        "orientation_error_deg=%.3f tolerance_mm=%.3f tolerance_deg=%.3f actual=%s target=%s",
        reached,
        position_error,
        orientation_error,
        float(position_tolerance_mm),
        float(orientation_tolerance_deg),
        [round(float(value), 3) for value in actual[:6]],
        [round(float(value), 3) for value in expected[:6]],
    )
    return reached


def _on_workpiece_release_verified(executor: object) -> tuple[bool, str]:
    """Notify the composed system after release verification succeeds."""
    if _dropoff_strategy_name(executor) == "plate_layout":
        service = getattr(executor, "_plate_layout_service", None)
        if service is None or service.pending is None:
            return False, "Workpiece released, but no plate-layout reservation was active"
        service.commit(executor._paint_process_config().dropoff)
        _logger.info("[PLATE_LAYOUT] Committed plate position after verified release")
        return True, ""
    callback = getattr(executor, "_on_workpiece_release_verified", None)
    if callback is None:
        return True, ""
    try:
        ok = bool(callback())
    except Exception:
        _logger.exception("[DROPOFF] Workpiece-release callback raised")
        return False, "Workpiece released, but the dryer sequence could not be queued"
    if not ok:
        _logger.error("[DROPOFF] Dryer sequence was rejected after workpiece release")
        return False, "Workpiece released, but the dryer sequence could not be queued"
    _logger.info("[DROPOFF] Dryer sequence queued after workpiece release verification")
    return True, ""


def _verify_workpiece_released(executor: object) -> tuple[bool, str]:
    """Verify that vacuum cleared after pump-off at the dropoff waypoint."""
    is_pump_enabled = getattr(executor, "_is_vacuum_pump_enabled", None)
    pump_enabled = (
        bool(is_pump_enabled())
        if callable(is_pump_enabled)
        else bool(getattr(executor, "_enable_vacuum_pump", True))
    )
    if not pump_enabled:
        _logger.info("[DROPOFF] Release verification skipped: vacuum pump disabled")
        return True, ""

    sensor = getattr(executor, "_vacuum_sensor", None)
    if sensor is None:
        _logger.warning("[DROPOFF] Release verification skipped: vacuum sensor not configured")
        return True, ""

    _logger.info("[DROPOFF] Verifying workpiece release with vacuum sensor")
    try:
        vacuum_detected = bool(sensor.is_vacuum_detected())
    except Exception:
        _logger.exception("[DROPOFF] Vacuum sensor read raised during release verification")
        return False, "Vacuum pump turned off, but workpiece release verification failed: sensor read unavailable"
    if not bool(sensor.is_healthy()):
        return False, "Vacuum pump turned off, but workpiece release verification failed: sensor read unavailable"
    if vacuum_detected:
        return False, "Vacuum pump turned off, but the vacuum sensor still detects the workpiece"

    _logger.info("[DROPOFF] Workpiece release verified: vacuum is no longer detected")
    return True, ""


def _build_dropoff_release_plan(executor: object) -> DropoffReleasePlan:
    strategy_name = _dropoff_strategy_name(executor)
    dropoff = executor._paint_process_config().dropoff
    if strategy_name == "pickup_origin":
        if _should_release_at_current_dropoff_pose(executor):
            return DropoffReleasePlan(
                strategy_name=strategy_name,
                waypoints=(
                    DropoffReleaseWaypoint(
                        label="Release at current dropoff pose",
                        pose=None,
                        vel_percent=dropoff.release_align_vel_percent,
                        acc_percent=dropoff.release_align_acc_percent,
                        motion_type=dropoff.release_align_motion_type,
                        blendR=dropoff.release_align_blendR,
                        release_here=True,
                    ),
                ),
            )
        pickup_plan = executor._last_pickup_plan
        if pickup_plan is None:
            _logger.info("[DROPOFF] pickup_origin has no pickup plan; releasing at current pose")
            return DropoffReleasePlan(
                strategy_name=strategy_name,
                waypoints=(
                    DropoffReleaseWaypoint(
                        label="Release at current pose",
                        pose=None,
                        vel_percent=dropoff.release_align_vel_percent,
                        acc_percent=dropoff.release_align_acc_percent,
                        motion_type=dropoff.release_align_motion_type,
                        blendR=dropoff.release_align_blendR,
                        release_here=True,
                    ),
                ),
            )
        return DropoffReleasePlan(
            strategy_name=strategy_name,
            waypoints=(
                DropoffReleaseWaypoint(
                    label="Returning to align pose for release",
                    pose=list(pickup_plan.align_pose),
                    vel_percent=dropoff.release_align_vel_percent,
                    acc_percent=dropoff.release_align_acc_percent,
                    motion_type=dropoff.release_align_motion_type,
                    blendR=dropoff.release_align_blendR,
                    release_here=True,
                ),
            ),
        )

    if strategy_name == "movement_group":
        pose = _resolve_dropoff_align_pose(executor)
        if pose is None:
            _logger.info("[DROPOFF] movement_group has no configured pose for group 'Dropoff'")
            return DropoffReleasePlan(strategy_name=strategy_name, waypoints=())
        if float(pose[2]) < 0.0:
            if not bool(getattr(dropoff, "allow_sub_zero_dropoff", False)):
                _logger.error("[DROPOFF] Negative target rejected: Allow Sub-Zero Dropoff is disabled")
                return DropoffReleasePlan(strategy_name=strategy_name, waypoints=())
            approach_pose = list(pose)
            approach_pose[2] = float(dropoff.sub_zero_approach_z_mm)
            corridor_id = getattr(executor, "_dropoff_motion_corridor_id", None)
            return DropoffReleasePlan(
                strategy_name=strategy_name,
                waypoints=(
                    DropoffReleaseWaypoint(
                        label="Moving above dropoff group 'Dropoff'",
                        pose=approach_pose,
                        vel_percent=dropoff.release_align_vel_percent,
                        acc_percent=dropoff.release_align_acc_percent,
                    ),
                    DropoffReleaseWaypoint(
                        label="Descending through dropoff group 'Dropoff' passage",
                        pose=pose,
                        vel_percent=dropoff.release_align_vel_percent,
                        acc_percent=dropoff.release_align_acc_percent,
                        motion_type="linear",
                        release_here=True,
                        corridor_id=corridor_id,
                    ),
                    DropoffReleaseWaypoint(
                        label="Retracting through dropoff group 'Dropoff' passage",
                        pose=approach_pose,
                        vel_percent=dropoff.release_align_vel_percent,
                        acc_percent=dropoff.release_align_acc_percent,
                        motion_type="linear",
                        corridor_id=corridor_id,
                    ),
                ),
            )
        return DropoffReleasePlan(
            strategy_name=strategy_name,
            waypoints=(
                DropoffReleaseWaypoint(
                    label="Moving to dropoff group 'Dropoff' for release",
                    pose=pose,
                    vel_percent=dropoff.release_align_vel_percent,
                    acc_percent=dropoff.release_align_acc_percent,
                    motion_type=dropoff.release_align_motion_type,
                    blendR=dropoff.release_align_blendR,
                    release_here=True,
                ),
            ),
        )

    if strategy_name == "plate_layout":
        service = getattr(executor, "_plate_layout_service", None)
        reservation = None if service is None else service.pending
        if reservation is None:
            _logger.error("[PLATE_LAYOUT] Dropoff requested without an active reservation")
            return DropoffReleasePlan(strategy_name=strategy_name, waypoints=())
        dropoff = executor._paint_process_config().dropoff
        center_to_approach = _plate_motion_profile(dropoff, "center_to_approach")
        descend_release = _plate_motion_profile(dropoff, "descend_release")
        retract_after_release = _plate_motion_profile(dropoff, "retract_after_release")
        return_plate_center = _plate_motion_profile(dropoff, "return_plate_center")
        return DropoffReleasePlan(
            strategy_name=strategy_name,
            waypoints=(
                DropoffReleaseWaypoint(
                    label="Moving above calculated plate position",
                    pose=list(reservation.approach_pose),
                    vel_percent=center_to_approach["vel_percent"],
                    acc_percent=center_to_approach["acc_percent"],
                    motion_type="linear",
                    blendR=center_to_approach["blendR"],
                    corridor_id=_plate_layout_corridor_id(executor),
                ),
                DropoffReleaseWaypoint(
                    label="Descending to calculated plate position",
                    pose=list(reservation.release_pose),
                    vel_percent=descend_release["vel_percent"],
                    acc_percent=descend_release["acc_percent"],
                    motion_type="linear",
                    blendR=descend_release["blendR"],
                    release_here=True,
                    corridor_id=_plate_layout_corridor_id(executor),
                ),
                DropoffReleaseWaypoint(
                    label="Retracting from calculated plate position",
                    pose=list(reservation.approach_pose),
                    vel_percent=retract_after_release["vel_percent"],
                    acc_percent=retract_after_release["acc_percent"],
                    motion_type="linear",
                    blendR=retract_after_release["blendR"],
                    corridor_id=_plate_layout_corridor_id(executor),
                ),
                DropoffReleaseWaypoint(
                    label="Returning through plate center",
                    pose=list(reservation.transit_pose),
                    vel_percent=return_plate_center["vel_percent"],
                    acc_percent=return_plate_center["acc_percent"],
                    motion_type="linear",
                    blendR=return_plate_center["blendR"],
                    corridor_id=_plate_layout_corridor_id(executor),
                ),
            ),
        )

    return DropoffReleasePlan(strategy_name=strategy_name, waypoints=())


def build_ordered_dropoff_preparation_segments(executor: object) -> tuple[list[dict], list[float] | None]:
    """
    Build the post-paint ordered dropoff preparation chain.

    This is the place to adjust ordered dropoff preparation move shape:

    - safe-travel segment labels
    - safe-travel/dropoff align velocity and acceleration
    - route `blendR`
    - final Joint 6 unwind segment settings
    """
    config = executor._paint_process_config()
    route_items: list[dict] = []

    safe_waypoints = _resolve_dropoff_safe_travel_waypoints(executor)
    if bool(config.dropoff_safe_travel.enabled):
        if not safe_waypoints:
            return [], None

        for index, safe_waypoint in enumerate(safe_waypoints, start=1):
            route_items.append(
                {
                    "label": f"prepare_dropoff_safe_travel_{index}",
                    "position": list(safe_waypoint["position"]),
                    "vel": float(safe_waypoint["vel_percent"]),
                    "acc": float(safe_waypoint["acc_percent"]),
                    "type": str(safe_waypoint.get("motion_type", "ptp")),
                    "blendR": float(safe_waypoint.get("blendR", 0.0)),
                }
            )

    if _should_prepare_dropoff_align_before_unwind(executor):
        reference_pose = route_items[-1]["position"] if route_items else executor._last_process_end_pose
        align_pose = _resolve_dropoff_preparation_pose(executor, reference_pose)
        if align_pose is None:
            return [], None

        route_items.append(
            {
                "label": "prepare_dropoff_align",
                "position": list(align_pose),
                "vel": float(config.dropoff.release_align_vel_percent),
                "acc": float(config.dropoff.release_align_acc_percent),
                "type": str(config.dropoff.release_align_motion_type),
                "blendR": float(config.dropoff.release_align_blendR),
            }
        )

    segments: list[dict] = []
    if route_items:
        start_pose = list(executor._last_process_end_pose) if executor._last_process_end_pose is not None else None
        adjusted_positions = _apply_distributed_dropoff_unwind(
            executor,
            [item["position"] for item in route_items],
            start_pose,
        )

        for index, (item, adjusted_position) in enumerate(zip(route_items, adjusted_positions)):
            is_last_route_pose = index == len(route_items) - 1
            segments.append(
                {
                    "type": str(item.get("type", "ptp")),
                    "label": item["label"],
                    "position": list(adjusted_position),
                    "vel": float(item["vel"]),
                    "acc": float(item["acc"]),
                    "blendR": float(item.get("blendR", 0.0 if is_last_route_pose else 20.0)),
                }
            )
        final_pose = list(adjusted_positions[-1])
    else:
        final_pose = list(executor._last_process_end_pose) if executor._last_process_end_pose is not None else None

    segments.append(
        {
            "type": "unwind_joint6",
            "label": "prepare_dropoff_unwind",
            "vel": float(config.navigation_return.unwind_vel_percent),
            "acc": float(config.navigation_return.unwind_acc_percent),
            "protected": True,
        }
    )

    release_pose = _resolve_dropoff_align_pose(executor, final_pose)
    if (
        release_pose is not None
        and len(release_pose) >= 3
        and float(release_pose[2]) < 0.0
        and bool(getattr(config.dropoff, "allow_sub_zero_dropoff", False))
    ):
        # Unwind above the opening, then make the corridor descent the final
        # protected segment. The ordered chain therefore hard-stops exactly at
        # the configured release pose; DROPOFF releases there and retracts.
        descent_pose = list(final_pose) if final_pose is not None else list(release_pose)
        descent_pose[2] = float(release_pose[2])
        segments.append(
            {
                "type": "linear",
                "label": "prepare_dropoff_descend_to_release",
                "position": descent_pose,
                "vel": float(config.dropoff.release_align_vel_percent),
                "acc": float(config.dropoff.release_align_acc_percent),
                "blendR": 0.0,
                "protected": True,
            }
        )
        final_pose = list(descent_pose)

    return segments, final_pose


def _resolve_dropoff_safe_travel_waypoints(executor: object) -> list[dict]:
    config = executor._paint_process_config().dropoff_safe_travel
    if not bool(config.enabled):
        return []
    dropoff = executor._paint_process_config().dropoff
    return executor._read_configured_waypoints(
        getattr(config, "positions", []),
        getattr(config, "position", []),
        float(dropoff.release_align_vel_percent),
        float(dropoff.release_align_acc_percent),
        "ptp",
    )


def _apply_distributed_dropoff_unwind(
    executor: object,
    poses: list[list[float]],
    start_pose: list[float] | None,
) -> list[list[float]]:
    """
    Progressively shift the active rotation component by whole-turn equivalents
    so Joint 6 can unwind while travelling toward dropoff.
    """
    if not poses:
        return []

    adjusted = [list(pose) for pose in poses]
    if start_pose is None or len(start_pose) < 6:
        return adjusted

    rotation_index = int(executor._contact_motion_config.rotation_index)
    if rotation_index < 0 or len(start_pose) <= rotation_index:
        return adjusted
    if any(len(pose) <= rotation_index for pose in adjusted):
        return adjusted

    start_rotation_deg = float(start_pose[rotation_index])
    nominal_continuous_rotations: list[float] = []
    previous_nominal_rotation_deg = start_rotation_deg

    for pose in adjusted:
        nominal_rotation_deg = float(pose[rotation_index])
        continuous_rotation_deg = unwrap_degrees(previous_nominal_rotation_deg, nominal_rotation_deg)
        nominal_continuous_rotations.append(continuous_rotation_deg)
        previous_nominal_rotation_deg = continuous_rotation_deg

    if not nominal_continuous_rotations:
        return adjusted

    final_nominal_continuous_deg = nominal_continuous_rotations[-1]
    final_canonical_deg = ((final_nominal_continuous_deg + 180.0) % 360.0) - 180.0
    unwind_shift_deg = final_canonical_deg - final_nominal_continuous_deg
    unwind_turns = int(round(unwind_shift_deg / 360.0))
    unwind_shift_deg = 360.0 * unwind_turns

    if unwind_turns == 0:
        _logger.info(
            "[DROPOFF] Distributed unwind not needed: start_rotation=%.3fdeg final_nominal_continuous=%.3fdeg",
            start_rotation_deg,
            final_nominal_continuous_deg,
        )
        return adjusted

    route = [list(start_pose), *adjusted]
    segment_lengths: list[float] = []
    for index in range(1, len(route)):
        previous_xyz = np.asarray(route[index - 1][:3], dtype=float)
        current_xyz = np.asarray(route[index][:3], dtype=float)
        segment_lengths.append(float(np.linalg.norm(current_xyz - previous_xyz)))

    total_distance = float(sum(segment_lengths))
    if total_distance <= 1e-6:
        _logger.warning("[DROPOFF] Distributed unwind skipped because dropoff route has no XYZ travel")
        return adjusted

    cumulative_distance = 0.0
    applied_rotations: list[float] = []
    for index, pose in enumerate(adjusted):
        cumulative_distance += segment_lengths[index]
        fraction = max(0.0, min(1.0, cumulative_distance / total_distance))
        final_rotation_deg = nominal_continuous_rotations[index] + (unwind_shift_deg * fraction)
        pose[rotation_index] = final_rotation_deg
        applied_rotations.append(final_rotation_deg)

    _logger.info(
        "[DROPOFF] Distributed unwind over travel: start_rotation=%.3fdeg nominal_rotations=%s unwind_turns=%d unwind_shift=%.3fdeg applied_rotations=%s travel_mm=%.3f",
        start_rotation_deg,
        [round(value, 3) for value in nominal_continuous_rotations],
        unwind_turns,
        unwind_shift_deg,
        [round(value, 3) for value in applied_rotations],
        total_distance,
    )
    return adjusted


def _should_prepare_dropoff_align_before_unwind(executor: object) -> bool:
    if _dropoff_strategy_name(executor) in {"movement_group", "plate_layout"}:
        return _resolve_dropoff_release_pose(executor) is not None
    return (
        executor._configured_contact_motion_plane == "xz_y_ry"
        and _resolve_dropoff_release_pose(executor) is not None
    )


def _should_release_at_current_dropoff_pose(executor: object) -> bool:
    return (
        executor._configured_contact_motion_plane == "xy_z_rz"
        and _dropoff_strategy_name(executor) == "pickup_origin"
    )


def _dropoff_strategy_name(executor: object) -> str:
    config_getter = getattr(executor, "_paint_process_config", None)
    if not callable(config_getter):
        return "pickup_origin"
    dropoff = getattr(config_getter(), "dropoff", None)
    return str(getattr(dropoff, "strategy", "pickup_origin") or "pickup_origin").strip().lower()


def _resolve_dropoff_release_pose(executor: object) -> list[float] | None:
    if _dropoff_strategy_name(executor) == "plate_layout":
        service = getattr(executor, "_plate_layout_service", None)
        reservation = None if service is None else service.pending
        return None if reservation is None else list(reservation.release_pose)
    if _dropoff_strategy_name(executor) == "movement_group":
        return executor._read_provider_position(executor._dropoff_position_provider)
    if executor._last_pickup_plan is not None and hasattr(executor._last_pickup_plan, "align_pose"):
        return list(executor._last_pickup_plan.align_pose)
    return None


def _resolve_dropoff_align_pose(executor: object, reference_pose: list[float] | None = None) -> list[float] | None:
    pose = _resolve_dropoff_release_pose(executor)
    if pose is None:
        return None
    return _dropoff_align_pose_near_reference(executor, pose, reference_pose)


def _resolve_dropoff_preparation_pose(
    executor: object,
    reference_pose: list[float] | None = None,
) -> list[float] | None:
    """Resolve the safe above-floor endpoint used before a corridor dropoff."""
    if _dropoff_strategy_name(executor) == "plate_layout":
        service = getattr(executor, "_plate_layout_service", None)
        reservation = None if service is None else service.pending
        return None if reservation is None else list(reservation.approach_pose)
    pose = _resolve_dropoff_align_pose(executor, reference_pose)
    if pose is None or len(pose) < 3 or float(pose[2]) >= 0.0:
        return pose
    dropoff = executor._paint_process_config().dropoff
    if not bool(getattr(dropoff, "allow_sub_zero_dropoff", False)):
        return pose
    approach_pose = list(pose)
    approach_pose[2] = float(dropoff.sub_zero_approach_z_mm)
    return approach_pose


def _plate_layout_corridor_id(executor: object) -> str:
    base_id = str(getattr(executor, "_dropoff_motion_corridor_id", "") or "paint_dropoff")
    return f"{base_id}_plate_layout"


def _plate_motion_profile(dropoff: object, key: str) -> dict[str, float]:
    fallback = {
        "vel_percent": float(dropoff.release_align_vel_percent),
        "acc_percent": float(dropoff.release_align_acc_percent),
        "blendR": float(dropoff.release_align_blendR),
    }
    for raw in list(getattr(dropoff, "plate_motion_profiles", []) or []):
        if isinstance(raw, dict) and str(raw.get("key", "")) == key:
            try:
                return {
                    "vel_percent": float(raw.get("vel_percent", fallback["vel_percent"])),
                    "acc_percent": float(raw.get("acc_percent", fallback["acc_percent"])),
                    "blendR": max(0.0, float(raw.get("blendR", fallback["blendR"]))),
                }
            except (TypeError, ValueError):
                break
    return fallback


def _execute_plate_layout_preparation(executor: object) -> tuple[bool, str]:
    """Enter the plate through its center and unwind without generic dropoff waypoints."""
    service = getattr(executor, "_plate_layout_service", None)
    reservation = None if service is None else service.pending
    if reservation is None:
        return False, "Plate-layout dropoff has no active reservation"

    config = executor._paint_process_config()
    enter_profile = _plate_motion_profile(config.dropoff, "enter_plate_center")
    register = getattr(executor._robot_service, "register_motion_corridor", None)
    current_getter = getattr(executor._robot_service, "get_current_position_fresh", None)
    if not callable(current_getter):
        current_getter = getattr(executor._robot_service, "get_current_position", None)
    if not callable(register) or not callable(current_getter):
        return False, "Plate-layout bounded transit is unavailable"
    try:
        current_pose = list(current_getter() or [])
    except Exception:
        _logger.exception("[PLATE_LAYOUT] Failed to read current pose for bounded transit")
        return False, "Plate-layout bounded transit could not read the current robot pose"
    if len(current_pose) < 3:
        current_pose = list(getattr(executor, "_last_process_end_pose", None) or [])
    if len(current_pose) < 3:
        return False, "Plate-layout bounded transit requires a valid current robot pose"

    from src.engine.robot.safety import MotionCorridor
    from src.robot_systems.paint.processes.paint.plate_layout import validate_plate_corners

    corners, error = validate_plate_corners(config.dropoff.plate_corners)
    if error:
        return False, error
    commanded_end_pose = list(getattr(executor, "_last_process_end_pose", None) or [])
    bounded_poses = [current_pose, reservation.transit_pose, reservation.approach_pose,
                     reservation.release_pose, *corners]
    if len(commanded_end_pose) >= 3:
        # The ordered-chain completion notification and live TCP telemetry can
        # arrive a few samples apart.  Bound the whole settling segment rather
        # than a single instantaneous sample so corridor entry is deterministic.
        bounded_poses.append(commanded_end_pose)
    padding_mm = _PLATE_LAYOUT_CORRIDOR_PADDING_MM
    corridor = MotionCorridor(
        corridor_id=_plate_layout_corridor_id(executor),
        x_min=min(float(pose[0]) for pose in bounded_poses) - padding_mm,
        x_max=max(float(pose[0]) for pose in bounded_poses) + padding_mm,
        y_min=min(float(pose[1]) for pose in bounded_poses) - padding_mm,
        y_max=max(float(pose[1]) for pose in bounded_poses) + padding_mm,
        z_min=min(float(pose[2]) for pose in bounded_poses) - padding_mm,
        entry_z_max=max(float(pose[2]) for pose in bounded_poses) + padding_mm,
        maximum_velocity=100.0,
        maximum_acceleration=100.0,
        allow_planar_transit=True,
    )
    try:
        register(corridor)
    except (TypeError, ValueError, NotImplementedError):
        _logger.exception("[PLATE_LAYOUT] Failed to register bounded transit corridor")
        return False, "Plate-layout bounded transit corridor could not be registered"
    _logger.info(
        "[PLATE_LAYOUT] Registered bounded transit corridor=%s current_xyz=%s commanded_end_xyz=%s "
        "bounds=x[%.3f, %.3f] y[%.3f, %.3f] z[%.3f, %.3f]",
        corridor.corridor_id,
        [round(float(value), 3) for value in current_pose[:3]],
        [round(float(value), 3) for value in commanded_end_pose[:3]],
        corridor.x_min,
        corridor.x_max,
        corridor.y_min,
        corridor.y_max,
        corridor.z_min,
        corridor.entry_z_max,
    )

    if not executor._motion.move_pickup_phase(
        "Moving through plate center before dropoff",
        list(reservation.transit_pose),
        velocity=enter_profile["vel_percent"],
        acceleration=enter_profile["acc_percent"],
        motion_type="linear",
        blendR=enter_profile["blendR"],
        corridor_id=corridor.corridor_id,
    ):
        return False, "Pivot paint finished, but bounded move to plate center failed"

    if not executor._robot_service.unwind_joint6(
        blocking=True,
        queue_if_busy=PAINT_PROCESS_CONFIG.navigation_return.unwind_queue_if_busy,
        vel=config.navigation_return.unwind_vel_percent,
        acc=config.navigation_return.unwind_acc_percent,
    ):
        return False, "Pivot paint finished, but Joint 6 unwind failed at plate center"
    executor._dropoff_unwind_prepared = True
    executor._last_process_end_pose = list(reservation.transit_pose)
    return True, ""


def _dropoff_align_pose_near_reference(
    executor: object,
    align_pose: list[float],
    reference_pose: list[float] | None = None,
) -> list[float]:
    pose = list(align_pose)
    reference = reference_pose or executor._last_process_end_pose
    if (
        executor._configured_contact_motion_plane == "xy_z_rz"
        and reference is not None
        and len(pose) >= 6
        and len(reference) >= 6
    ):
        pose[5] = unwrap_degrees(float(reference[5]), float(pose[5]))
    return pose


def _poses_close(left: list[float] | None, right: list[float] | None, tolerance: float = 1e-3) -> bool:
    if left is None or right is None or len(left) < 6 or len(right) < 6:
        return False
    if not all(abs(float(a) - float(b)) <= tolerance for a, b in zip(left[:5], right[:5])):
        return False
    equivalent_rz = unwrap_degrees(float(right[5]), float(left[5]))
    return abs(equivalent_rz - float(right[5])) <= tolerance

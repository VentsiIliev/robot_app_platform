from __future__ import annotations

import logging
import math
import time

from src.engine.robot.enums.axis import Direction, RobotAxis
from src.engine.robot.procedures import (
    ServoRetractConfig,
    ServoUntilConditionConfig,
    ServoUntilConditionProcedure,
)
from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_load_handler import (
    interrupted_or_error,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.processes.paint.config import (
    PICKUP_CONTACT_MODE_HEIGHT_MEASURE,
    PICKUP_CONTACT_MODE_PLANNED,
    PICKUP_CONTACT_MODE_SERVO_CONTACT,
)
from src.robot_systems.paint.processes.paint.execute.pickup_executor import (
    build_magazine_pickup_release_segments,
    normalize_pickup_contact_mode,
)
from src.robot_systems.paint.timing import timed_step

_logger = logging.getLogger(__name__)


@timed_step(_logger, "pickup_target_to_position_release")
def execute_magazine_pickup_release(
    load_service: object,
    *,
    pickup_xy: tuple[float, float] | list[float],
    pickup_rz: float,
    pickup_base_pose: list[float],
    release_pose: list[float],
    workpiece_height_mm: float = 0.0,
    release_label: str = "release",
    resume_from_current_pose: bool = False,
) -> tuple[bool, str]:
    """Pick up a resolved magazine target and release it at an explicit pose."""
    executor = load_service._path_executor
    executor._refresh_paint_process_config_snapshot()
    executor._apply_paint_process_contact_config()
    executor._refresh_runtime_config()
    if pickup_xy is None or len(pickup_xy) < 2:
        return False, "Pickup target XY is not configured"
    if pickup_base_pose is None or len(pickup_base_pose) < 6:
        return False, "Pickup base pose is not configured"
    if release_pose is None or len(release_pose) < 6:
        return False, f"{release_label.capitalize()} pose is not configured"

    pickup_motion = executor._paint_process_config().pickup_motion
    pickup_z = executor._pickup_z_mm
    if pickup_z is None:
        pickup_z = (
            executor._pickup_safety_z_min_mm
            + float(workpiece_height_mm or 0.0)
            + pickup_motion.contact_offset_mm
        )

    pickup_x = float(pickup_xy[0])
    pickup_y = float(pickup_xy[1])
    pickup_rx = float(pickup_base_pose[3])
    pickup_ry = float(pickup_base_pose[4])
    pickup_rz = float(pickup_rz)
    approach_pose = [
        pickup_x,
        pickup_y,
        float(pickup_z) + pickup_motion.approach_offset_mm,
        pickup_rx,
        pickup_ry,
        pickup_rz,
    ]
    pickup_pose = [pickup_x, pickup_y, float(pickup_z), pickup_rx, pickup_ry, pickup_rz]
    lift_pose = [
        pickup_x,
        pickup_y,
        float(pickup_z) + min(
            pickup_motion.initial_lift_clearance_mm,
            pickup_motion.approach_offset_mm,
        ),
        pickup_rx,
        pickup_ry,
        pickup_rz,
    ]

    _logger.info(
        "[MAGAZINE_LOAD] pickup target xy=(%.3f, %.3f) rz=%.3f workpiece_height=%.3f pickup_z=%.3f safety_z_min=%.3f",
        pickup_x,
        pickup_y,
        pickup_rz,
        float(workpiece_height_mm or 0.0),
        float(pickup_z),
        executor._pickup_safety_z_min_mm,
    )

    transfer_waypoints = (
        (
            "Moving to magazine pickup approach pose",
            approach_pose,
            pickup_motion.approach_vel_percent,
            pickup_motion.approach_acc_percent,
            pickup_motion.approach_motion_type,
            pickup_motion.approach_blendR,
        ),
        (
            "Descending to magazine pickup pose",
            pickup_pose,
            pickup_motion.descend_vel_percent,
            pickup_motion.descend_acc_percent,
            pickup_motion.descend_motion_type,
            pickup_motion.descend_blendR,
        ),
        (
            "Lifting magazine workpiece",
            lift_pose,
            pickup_motion.lift_align_vel_percent,
            pickup_motion.lift_align_acc_percent,
            pickup_motion.lift_align_motion_type,
            pickup_motion.lift_align_blendR,
        ),
    )
    magazine_config = executor._paint_process_config().magazine_load
    velocity = float(magazine_config.transfer_to_calibration_vel_percent)
    acceleration = float(magazine_config.transfer_to_calibration_acc_percent)
    release_move_label = f"Moving picked workpiece to {release_label} release pose"
    transfer_waypoints = transfer_waypoints + (
        (
            release_move_label,
            list(release_pose),
            velocity,
            acceleration,
            magazine_config.transfer_to_calibration_motion_type,
            magazine_config.transfer_to_calibration_blendR,
        ),
    )

    contact_mode = normalize_pickup_contact_mode(pickup_motion.magazine_pickup_contact_mode)
    ordered_segments = build_magazine_pickup_release_segments(transfer_waypoints)

    if resume_from_current_pose:
        if contact_mode != PICKUP_CONTACT_MODE_PLANNED:
            _logger.info(
                "[MAGAZINE_LOAD] Contact-mode pickup resume requested; using planned resume path mode=%s",
                contact_mode,
            )
            contact_mode = PICKUP_CONTACT_MODE_PLANNED
        ordered_segments = executor._motion.trim_ordered_pickup_segments_from_current_pose(ordered_segments)
    if not ordered_segments:
        _logger.info("[PICKUP] Ordered magazine pickup-to-release sequence already at final target")
    else:
        ok, msg = executor._motion.turn_vacuum_on(
            required=contact_mode == PICKUP_CONTACT_MODE_SERVO_CONTACT,
        )
        if not ok:
            return False, msg
        if contact_mode == PICKUP_CONTACT_MODE_SERVO_CONTACT:
            ok, msg = _execute_magazine_servo_contact_pickup_release(
                executor,
                transfer_waypoints,
                retract_reference_pose=pickup_base_pose,
                release_label=release_label,
            )
        elif contact_mode == PICKUP_CONTACT_MODE_HEIGHT_MEASURE:
            _logger.error(
                "[MAGAZINE_LOAD] Height-measured pickup Z mode is selected, but height service wiring is not implemented yet"
            )
            ok = False
            msg = "Magazine height-measured pickup Z mode is not wired yet"
        elif contact_mode == PICKUP_CONTACT_MODE_PLANNED:
            ok = executor._motion.move_ordered_pickup_sequence(
                "Ordered magazine pickup-to-release sequence",
                ordered_segments,
            )
            msg = f"Move to {release_label} release pose failed"
        else:
            _logger.error("[MAGAZINE_LOAD] Invalid magazine pickup contact mode: %s", contact_mode)
            ok = False
            msg = f"Invalid magazine pickup contact mode: {contact_mode}"
        if not ok:
            return False, msg

    ok, msg = executor._motion.turn_vacuum_off()
    if not ok:
        return False, msg
    return True, f"Workpiece transferred to {release_label}"


def _execute_magazine_servo_contact_pickup_release(
    executor,
    transfer_waypoints: tuple[tuple, ...],
    *,
    retract_reference_pose: list[float],
    release_label: str,
) -> tuple[bool, str]:
    pickup_motion = executor._paint_process_config().pickup_motion
    condition = getattr(executor, "_pickup_condition", None)
    if condition is None:
        _logger.error("[MAGAZINE_LOAD] Servo contact pickup requested, but no pickup condition is configured")
        return False, "Servo contact pickup condition is not configured"

    approach_segments = build_magazine_pickup_release_segments(transfer_waypoints[:1])
    safe_clearance_pose = list(transfer_waypoints[1][1])
    safe_clearance_pose[2] = float(retract_reference_pose[2])
    if not executor._motion.move_ordered_pickup_sequence(
        "Magazine pickup approach before servo contact",
        approach_segments,
    ):
        return False, "Magazine pickup approach before servo contact failed"

    contact_speed_mm_s = float(pickup_motion.servo_contact_linear_mm_s)
    minimum_contact_z_mm = float(getattr(pickup_motion, "servo_contact_min_z_mm", 0.0))
    _logger.info(
        "[MAGAZINE_LOAD] Servo contact descent starting: speed_mm_s=%.3f timeout_s=%.3f tool=%d user=%d",
        contact_speed_mm_s,
        float(pickup_motion.servo_contact_timeout_s),
        int(executor._pickup_tool),
        int(executor._pickup_user),
    )
    control = getattr(executor, "_active_execution_control", None)
    result = ServoUntilConditionProcedure(executor._robot_service, condition).run(
        config=ServoUntilConditionConfig(
            axis=RobotAxis.Z,
            direction=Direction.MINUS,
            linear_mm_s=contact_speed_mm_s,
            frame="user",
            tool=int(executor._pickup_tool),
            user=int(executor._pickup_user),
            poll_interval_s=float(pickup_motion.servo_contact_poll_interval_s),
            timeout_s=float(pickup_motion.servo_contact_timeout_s),
            preflight_condition_read_attempts=int(pickup_motion.servo_contact_preflight_read_attempts),
            condition_read_failure_limit=int(pickup_motion.servo_contact_read_failure_limit),
            allow_subzero_descent=True,
            disable_collision_checking=True,
            minimum_z_mm=minimum_contact_z_mm,
        ),
        retract=ServoRetractConfig(
            distance_mm=float(getattr(pickup_motion, "servo_contact_retract_distance_mm", 10.0)),
            motion_type="servo",
            linear_mm_s=float(getattr(pickup_motion, "servo_contact_retract_linear_mm_s", 25.0)),
            poll_interval_s=float(pickup_motion.servo_contact_poll_interval_s),
            timeout_s=3.0,
            position_tolerance_mm=2.0,
            maximum_distance_mm=float(
                getattr(pickup_motion, "servo_contact_retract_maximum_distance_mm", 50.0)
            ),
        ),
        cancel_requested=(
            None
            if control is None
            else lambda: bool(control.should_stop() or control.pause_requested())
        ),
    )
    _logger.info(
        "[MAGAZINE_LOAD] Servo contact descent result success=%s detected=%s timeout=%s elapsed_s=%.3f message=%s",
        result.success,
        result.detected,
        result.timed_out,
        result.elapsed_s,
        result.message,
    )
    if not result.success:
        return False, f"Magazine servo contact pickup failed: {result.message}"

    current_pose = _wait_for_stable_pose(executor._robot_service)
    if current_pose is None:
        return False, "Magazine post-retract pose did not become stable"
    clearance_distance = float(retract_reference_pose[2]) - float(current_pose[2])
    if clearance_distance <= 0.0 or clearance_distance > 500.0:
        return False, f"Magazine clearance distance is invalid: {clearance_distance:.3f} mm"

    # Plan the lift and release together from the measured post-Servo pose.
    # The first target is known, but the chain start is always live; this keeps
    # the blend safe without executing from an expected Servo endpoint.
    lift_waypoint = transfer_waypoints[2]
    lift_segment = (
        "Raising magazine workpiece to safe transfer clearance",
        safe_clearance_pose,
        lift_waypoint[2],
        lift_waypoint[3],
        lift_waypoint[4],
        10.0,
    )
    continuation_segments = build_magazine_pickup_release_segments(
        (lift_segment,) + transfer_waypoints[3:]
    )
    ok = executor._motion.move_ordered_pickup_sequence(
        f"Magazine lift and {release_label} release after completed servo retract",
        continuation_segments,
    )
    if not ok:
        reason = getattr(executor._motion, "last_motion_error", None)
        return False, f"Magazine {release_label} failed: {reason or 'ordered motion failed'}"
    return True, ""


def _read_fresh_pose(robot_service) -> list[float] | None:
    getter = getattr(robot_service, "get_current_position_fresh", None)
    if not callable(getter):
        getter = getattr(robot_service, "get_current_position", None)
    if not callable(getter):
        return None
    try:
        pose = getter()
    except Exception:
        _logger.exception("[MAGAZINE_LOAD] Failed to read current pose after servo contact")
        return None
    if pose is None or len(pose) < 6:
        return None
    return [float(value) for value in pose[:6]]


def _wait_for_stable_pose(
    robot_service,
    *,
    timeout_s: float = 1.0,
    sample_interval_s: float = 0.05,
    required_stable_samples: int = 3,
    xyz_tolerance_mm: float = 0.5,
    angular_tolerance_deg: float = 0.2,
) -> list[float] | None:
    """Confirm the Servo stop has physically settled before planning from it."""
    deadline = time.monotonic() + max(0.1, float(timeout_s))
    previous = None
    stable_samples = 0
    while time.monotonic() < deadline:
        pose = _read_fresh_pose(robot_service)
        if pose is None:
            stable_samples = 0
            previous = None
        elif previous is not None:
            xyz_delta = math.sqrt(sum(
                (pose[index] - previous[index]) ** 2 for index in range(3)
            ))
            angular_delta = max(
                abs((pose[index] - previous[index] + 180.0) % 360.0 - 180.0)
                for index in range(3, 6)
            )
            if xyz_delta <= xyz_tolerance_mm and angular_delta <= angular_tolerance_deg:
                stable_samples += 1
                if stable_samples >= max(1, int(required_stable_samples)):
                    _logger.info(
                        "[MAGAZINE_LOAD] Post-retract pose stable: xyz_delta_mm=%.3f "
                        "angular_delta_deg=%.3f samples=%d pose=%s",
                        xyz_delta,
                        angular_delta,
                        stable_samples,
                        [round(value, 3) for value in pose],
                    )
                    return pose
            else:
                stable_samples = 0
            previous = pose
        else:
            previous = pose
        time.sleep(max(0.01, float(sample_interval_s)))
    _logger.error("[MAGAZINE_LOAD] Post-retract pose stability timeout")
    return None


def handle_magazine_execute_pickup_release(ctx: PaintExecutionContext) -> PaintExecutionState:
    guarded = guard_control(ctx, PaintExecutionState.MAGAZINE_EXECUTE_PICKUP_RELEASE)
    if guarded is not None:
        return guarded

    load_service = ctx.production_service._magazine_load_service
    ok, msg = execute_magazine_pickup_release(
        load_service,
        pickup_xy=ctx.magazine_target["pickup_xy"],
        pickup_rz=ctx.magazine_target["pickup_rz"],
        pickup_base_pose=ctx.magazine_pose,
        release_pose=ctx.magazine_release_pose,
        workpiece_height_mm=0.0,
        release_label=f"{load_service._release_work_area_id} work area center",
        resume_from_current_pose=ctx.consume_resume_retry(),
    )
    if not ok:
        return interrupted_or_error(
            ctx,
            PaintExecutionState.MAGAZINE_EXECUTE_PICKUP_RELEASE,
            f"Magazine contour: {msg}",
        )
    ctx.set_result(True, f"Magazine contour: {msg}")
    return PaintExecutionState.MAGAZINE_MOVE_TO_CALIBRATION

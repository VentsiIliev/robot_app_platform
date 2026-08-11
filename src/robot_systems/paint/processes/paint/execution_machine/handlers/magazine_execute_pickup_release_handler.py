from __future__ import annotations

import logging

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load_handler import (
    interrupted_or_error,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.processes.paint.execute.pickup_executor import (
    build_magazine_pickup_release_segments,
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

    ordered_segments = build_magazine_pickup_release_segments(transfer_waypoints)

    if resume_from_current_pose:
        ordered_segments = executor._motion.trim_ordered_pickup_segments_from_current_pose(ordered_segments)
    if not ordered_segments:
        _logger.info("[PICKUP] Ordered magazine pickup-to-release sequence already at final target")
    else:
        ok, msg = executor._motion.turn_vacuum_on()
        if not ok:
            return False, msg
        if not executor._motion.move_ordered_pickup_sequence(
            "Ordered magazine pickup-to-release sequence",
            ordered_segments,
        ):
            return False, f"Move to {release_label} release pose failed"

    ok, msg = executor._motion.turn_vacuum_off()
    if not ok:
        return False, msg
    return True, f"Workpiece transferred to {release_label}"


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

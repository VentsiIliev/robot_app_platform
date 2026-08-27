from __future__ import annotations

import logging
from time import perf_counter

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.processes.paint.config import (
    MAGAZINE_PICKUP_TARGET_MODE_FIXED_GROUP,
    MAGAZINE_PICKUP_TARGET_MODE_VISION,
    PICKUP_CONTACT_MODE_SERVO_CONTACT,
)

_logger = logging.getLogger(__name__)


def handle_magazine_prepare_pickup_release(ctx: PaintExecutionContext) -> PaintExecutionState:
    guarded = guard_control(ctx, PaintExecutionState.MAGAZINE_PREPARE_PICKUP_RELEASE)
    if guarded is not None:
        return guarded

    service = ctx.production_service
    load_service = service._magazine_load_service
    started = perf_counter()

    magazine_pose_started = perf_counter()
    ctx.magazine_pose = load_service._navigation.get_group_position(ctx.magazine_group)
    magazine_pose_elapsed = perf_counter() - magazine_pose_started
    if ctx.magazine_pose is None:
        ctx.set_result(False, f"Magazine movement group '{ctx.magazine_group}' is not configured")
        return PaintExecutionState.ERROR

    release_base_started = perf_counter()
    base_release_pose = load_service._navigation.get_group_position(ctx.calibration_group)
    release_base_elapsed = perf_counter() - release_base_started
    if base_release_pose is None:
        ctx.set_result(False, f"Calibration movement group '{ctx.calibration_group}' is not configured")
        return PaintExecutionState.ERROR

    target_mode = str(
        ctx.magazine_config.pickup_target_mode or MAGAZINE_PICKUP_TARGET_MODE_VISION
    ).strip().lower()
    pickup_started = perf_counter()
    if target_mode == MAGAZINE_PICKUP_TARGET_MODE_FIXED_GROUP:
        process_config = ctx.process_config
        if process_config is None:
            ctx.set_result(False, "Paint process configuration is unavailable")
            return PaintExecutionState.ERROR
        contact_mode = str(process_config.pickup_motion.magazine_pickup_contact_mode).strip().lower()
        if contact_mode != PICKUP_CONTACT_MODE_SERVO_CONTACT:
            ctx.set_result(False, "Fixed-group magazine pickup requires servo_contact mode")
            return PaintExecutionState.ERROR
        ctx.magazine_fixed_pickup_pose = load_service._validated_pose(ctx.magazine_pose)
        if ctx.magazine_fixed_pickup_pose is None:
            ctx.set_result(False, f"Fixed magazine pickup group '{ctx.magazine_group}' has an invalid pose")
            return PaintExecutionState.ERROR
        ctx.magazine_target = {
            "pickup_xy": tuple(ctx.magazine_fixed_pickup_pose[:2]),
            "pickup_rz": float(ctx.magazine_fixed_pickup_pose[5]),
        }
    else:
        ctx.magazine_target = load_service._resolve_pickup_target(ctx.magazine_contour, ctx.magazine_pose)
        if ctx.magazine_target is None:
            ctx.set_result(False, "Could not resolve magazine pickup target")
            return PaintExecutionState.ERROR
    pickup_elapsed = perf_counter() - pickup_started

    release_started = perf_counter()
    if target_mode == MAGAZINE_PICKUP_TARGET_MODE_FIXED_GROUP:
        ctx.magazine_release_pose = list(base_release_pose)
        ctx.magazine_release_pose[2] = float(ctx.magazine_config.release_z_mm)
    else:
        ctx.magazine_release_pose = load_service._resolve_work_area_center_release_pose(
            base_pose=base_release_pose,
            frame=getattr(ctx.magazine_snapshot, "frame", None),
            release_z_mm=float(ctx.magazine_config.release_z_mm),
        )
    release_elapsed = perf_counter() - release_started
    if ctx.magazine_release_pose is None:
        ctx.set_result(False, f"Could not resolve {load_service._release_work_area_id} work area center release pose")
        return PaintExecutionState.ERROR

    _logger.info(
        "[MAGAZINE_LOAD_TIMING] prepare_pickup_release magazine_pose_s=%.3f release_base_pose_s=%.3f "
        "pickup_target_s=%.3f release_pose_s=%.3f total_s=%.3f",
        magazine_pose_elapsed,
        release_base_elapsed,
        pickup_elapsed,
        release_elapsed,
        perf_counter() - started,
    )
    return PaintExecutionState.MAGAZINE_EXECUTE_PICKUP_RELEASE

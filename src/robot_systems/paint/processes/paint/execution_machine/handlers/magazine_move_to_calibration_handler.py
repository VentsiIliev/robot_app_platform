from __future__ import annotations

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load_handler import (
    interrupted_or_error,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState


def handle_magazine_move_to_calibration(ctx: PaintExecutionContext) -> PaintExecutionState:
    guarded = guard_control(ctx, PaintExecutionState.MAGAZINE_MOVE_TO_CALIBRATION)
    if guarded is not None:
        return guarded

    load_service = ctx.production_service._magazine_load_service
    config = ctx.magazine_config
    ok = load_service._move_to_group_with_pause_resume_recovery(
        ctx,
        PaintExecutionState.MAGAZINE_MOVE_TO_CALIBRATION,
        ctx.calibration_group,
        velocity=float(config.transfer_to_calibration_vel_percent),
        acceleration=float(config.transfer_to_calibration_acc_percent),
        motion_type=config.transfer_to_calibration_motion_type,
        blendR=float(config.transfer_to_calibration_blendR),
    )
    if not ok:
        return interrupted_or_error(
            ctx,
            PaintExecutionState.MAGAZINE_MOVE_TO_CALIBRATION,
            f"Move to calibration group '{ctx.calibration_group}' after release failed",
        )

    mark_verified = getattr(load_service._navigation, "mark_group_observed_area_verified", None)
    if callable(mark_verified):
        mark_verified(ctx.calibration_group)
    return PaintExecutionState.CALIBRATION_WAIT_CAMERA_SETTLE

from __future__ import annotations

import logging

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_load_handler import (
    interrupted_or_error,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState

_logger = logging.getLogger(__name__)


def handle_magazine_move_to_magazine(ctx: PaintExecutionContext) -> PaintExecutionState:
    service = ctx.production_service
    load_service = service._magazine_load_service
    config = ctx.magazine_config
    if load_service is None or config is None:
        return PaintExecutionState.CAPTURE_WORKPIECE

    guarded = guard_control(ctx, PaintExecutionState.MAGAZINE_MOVE_TO_MAGAZINE)
    if guarded is not None:
        return guarded

    if not ctx.magazine_group:
        ctx.magazine_group = str(config.magazine_group_id or "Magazine").strip()
    if not ctx.calibration_group:
        ctx.calibration_group = str(config.calibration_group_id or "CALIBRATION").strip()
    if not ctx.magazine_group:
        ctx.set_result(False, "Magazine movement group is not configured")
        return PaintExecutionState.ERROR
    if not ctx.calibration_group:
        ctx.set_result(False, "Calibration movement group is not configured")
        return PaintExecutionState.ERROR

    ok = load_service._move_to_group_with_pause_resume_recovery(
        ctx,
        PaintExecutionState.MAGAZINE_MOVE_TO_MAGAZINE,
        ctx.magazine_group,
        velocity=float(config.move_to_magazine_vel_percent),
        acceleration=float(config.move_to_magazine_acc_percent),
        motion_type=config.move_to_magazine_motion_type,
        blendR=float(config.move_to_magazine_blendR),
    )
    if not ok:
        return interrupted_or_error(
            ctx,
            PaintExecutionState.MAGAZINE_MOVE_TO_MAGAZINE,
            f"Move to magazine group '{ctx.magazine_group}' failed",
        )
    _logger.info("[MAGAZINE_LOAD] Moved to magazine group '%s'", ctx.magazine_group)
    return PaintExecutionState.MAGAZINE_WAIT_CAMERA_SETTLE

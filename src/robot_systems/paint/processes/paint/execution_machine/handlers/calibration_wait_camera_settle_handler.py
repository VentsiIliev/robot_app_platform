from __future__ import annotations

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load_handler import (
    interrupted_or_error,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState


def handle_calibration_wait_camera_settle(ctx: PaintExecutionContext) -> PaintExecutionState:
    guarded = guard_control(ctx, PaintExecutionState.CALIBRATION_WAIT_CAMERA_SETTLE)
    if guarded is not None:
        return guarded

    config = ctx.magazine_config
    if config is None:
        return PaintExecutionState.CAPTURE_WORKPIECE
    if not ctx.production_service._magazine_load_service._wait(
        config.release_settle_s,
        ctx.motion_cancel_requested,
    ):
        return interrupted_or_error(
            ctx,
            PaintExecutionState.CALIBRATION_WAIT_CAMERA_SETTLE,
            "Paint process stopped",
        )
    return PaintExecutionState.CAPTURE_WORKPIECE

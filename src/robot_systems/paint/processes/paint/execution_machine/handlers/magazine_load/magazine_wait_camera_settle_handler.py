from __future__ import annotations

import logging
from time import perf_counter

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_load_handler import (
    interrupted_or_error,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState

_logger = logging.getLogger(__name__)


def handle_magazine_wait_camera_settle(ctx: PaintExecutionContext) -> PaintExecutionState:
    guarded = guard_control(ctx, PaintExecutionState.MAGAZINE_WAIT_CAMERA_SETTLE)
    if guarded is not None:
        return guarded

    started = perf_counter()
    if not ctx.production_service._magazine_load_service._wait(
        ctx.magazine_config.camera_settle_s,
        ctx.motion_cancel_requested,
    ):
        return interrupted_or_error(
            ctx,
            PaintExecutionState.MAGAZINE_WAIT_CAMERA_SETTLE,
            "Paint process stopped",
        )
    _logger.info(
        "[MAGAZINE_LOAD_TIMING] wait_camera_settle configured_s=%.3f elapsed_s=%.3f",
        float(ctx.magazine_config.camera_settle_s),
        perf_counter() - started,
    )
    return PaintExecutionState.MAGAZINE_CAPTURE

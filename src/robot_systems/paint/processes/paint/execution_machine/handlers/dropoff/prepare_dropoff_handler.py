from __future__ import annotations

import logging

from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.dropoff_handlers import (
    execute_dropoff_preparation_for_executor,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.motion_handlers import (
    finish_paint_motion,
    set_paint_result,
    wait_or_guard,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState

_logger = logging.getLogger(__name__)


def handle_prepare_dropoff(ctx: PaintExecutionContext) -> PaintExecutionState:
    executor = ctx.production_service._path_executor

    guarded = wait_or_guard(ctx, PaintExecutionState.PREPARE_DROPOFF)
    if guarded is not None:
        finish_paint_motion(ctx, success=False)
        return guarded

    ok, msg = execute_dropoff_preparation_for_executor(executor)
    if not ok:
        log_timing(ctx, "prepare_dropoff")
        set_paint_result(ctx, False, msg)
        finish_paint_motion(ctx, success=False)
        return PaintExecutionState.ERROR
    executor._dropoff_unwind_prepared = True
    return PaintExecutionState.DROPOFF


def log_timing(ctx: PaintExecutionContext, stage: str) -> None:
    _logger.debug(
        "[TIMING] paint_process success=false stage=%s total_elapsed_s=%.3f",
        stage,
        elapsed_s(ctx.paint_started_at),
    )
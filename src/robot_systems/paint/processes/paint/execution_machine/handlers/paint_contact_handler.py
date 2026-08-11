from __future__ import annotations

import logging

from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.motion_handlers import (
    fail_paint_motion,
    finish_paint_motion,
    wait_or_guard,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState

_logger = logging.getLogger(__name__)


def handle_paint_contact(ctx: PaintExecutionContext) -> PaintExecutionState:
    executor = ctx.production_service._path_executor

    guarded = wait_or_guard(ctx, PaintExecutionState.PAINT_CONTACT)
    if guarded is not None:
        finish_paint_motion(ctx, success=False)
        return guarded

    if ctx.paint_contact_executed_in_ordered_chain:
        return PaintExecutionState.EDGE_CLEANUP

    ok, msg, total_waypoints = executor._paint_contact.execute(ctx.execution_plan, control=ctx.control)
    ctx.paint_total_waypoints = int(total_waypoints)
    if not ok:
        executor._edge_cleanup.cancel_early_preplanning()
        _logger.info(
            "[TIMING] paint_process success=false stage=contact total_elapsed_s=%.3f",
            elapsed_s(ctx.paint_started_at),
        )
        fail_paint_motion(ctx, msg)
        return PaintExecutionState.ERROR
    return PaintExecutionState.EDGE_CLEANUP

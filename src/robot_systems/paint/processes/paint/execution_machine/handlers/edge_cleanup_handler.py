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


def handle_edge_cleanup(ctx: PaintExecutionContext) -> PaintExecutionState:
    executor = ctx.production_service._path_executor

    guarded = wait_or_guard(ctx, PaintExecutionState.EDGE_CLEANUP)
    if guarded is not None:
        finish_paint_motion(ctx, success=False)
        return guarded

    if executor._edge_cleanup.should_run_after_xz_ry():
        ok, msg, cleanup_waypoints = executor._edge_cleanup.execute_after_unwind(
            ctx.execution_plan,
            ctx.paint_started_at,
        )
        ctx.paint_total_waypoints += int(cleanup_waypoints)
        if not ok:
            fail_paint_motion(ctx, msg)
            return PaintExecutionState.ERROR
    elif executor._edge_cleanup.should_run_after_xy_rz():
        ok, msg, cleanup_waypoints = executor._edge_cleanup.execute_after_xy_rz_paint(
            ctx.execution_plan,
            ctx.paint_started_at,
            unwind_before_cleanup=True,
        )
        ctx.paint_total_waypoints += int(cleanup_waypoints)
        if not ok:
            _logger.info(
                "[TIMING] paint_process success=false stage=edge_cleanup_xy_rz total_elapsed_s=%.3f",
                elapsed_s(ctx.paint_started_at),
            )
            fail_paint_motion(ctx, msg)
            return PaintExecutionState.ERROR
    return PaintExecutionState.PREPARE_DROPOFF

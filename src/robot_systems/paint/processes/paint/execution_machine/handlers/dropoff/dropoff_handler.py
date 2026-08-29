from __future__ import annotations

import logging

from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.dropoff_handlers import (
    execute_dropoff_release_for_executor,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.motion_handlers import (
    finish_paint_motion,
    set_paint_result,
    wait_or_guard,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState

_logger = logging.getLogger(__name__)


def handle_dropoff(ctx: PaintExecutionContext) -> PaintExecutionState:
    guarded = wait_or_guard(ctx, PaintExecutionState.DROPOFF)
    if guarded is not None:
        finish_paint_motion(ctx, success=False)
        return guarded

    service = ctx.production_service
    executor = service._path_executor
    next_cycle_start = service._next_cycle_start_target(ctx)
    ok, msg = execute_dropoff_release_for_executor(
        executor,
        next_cycle_start=next_cycle_start,
    )
    if not ok:
        _logger.info(
            "[TIMING] paint_process success=false stage=pre_release_dropoff total_elapsed_s=%.3f",
            elapsed_s(ctx.paint_started_at),
        )
        set_paint_result(ctx, False, msg)
        finish_paint_motion(ctx, success=False)
        return PaintExecutionState.ERROR

    prepositioned_group = getattr(executor, "_last_prepositioned_start_group", None)
    if prepositioned_group:
        service._mark_prepositioned_start_group(prepositioned_group)

    _logger.info(
        "[EXECUTE] Paint process completed: jobs=%d total_waypoints=%d",
        len(ctx.execution_plan.execution_jobs),
        ctx.paint_total_waypoints,
    )
    set_paint_result(
        ctx,
        True,
        (
            f"Paint process completed for "
            f"{len(ctx.execution_plan.execution_jobs)} path(s), {ctx.paint_total_waypoints} waypoints"
        ),
    )
    return PaintExecutionState.POST_RETURN

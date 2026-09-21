from __future__ import annotations

import logging

from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.config import DropoffStrategy
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
        log_timing(ctx, "pre_release_dropoff")

        set_paint_result(ctx, False, msg)
        finish_paint_motion(ctx, success=False)
        return PaintExecutionState.ERROR

    prepositioned_group = executor._last_prepositioned_start_group
    if prepositioned_group:
        service._mark_prepositioned_start_group(prepositioned_group)

    log_completion(ctx)

    plate_service = executor._plate_layout_service
    plate_is_full = (
        executor._paint_process_config().dropoff.strategy is DropoffStrategy.PLATE_LAYOUT
        and plate_service is not None
        and not plate_service.has_space_for_same_footprint
    )

    set_paint_result(
        ctx,
        True,
        (
            "Drop-off plate has no space for another workpiece of the same footprint"
            if plate_is_full
            else f"Paint process completed for {len(ctx.execution_plan.execution_jobs)} path(s), "
                 f"{ctx.paint_total_waypoints} waypoints"
        ),
    )
    return PaintExecutionState.POST_RETURN


def log_timing(ctx: PaintExecutionContext, stage: str) -> None:
    _logger.debug(
        "[TIMING] paint_process success=%s stage=%s total_elapsed_s=%.3f",
        ctx.result_ok,
        stage,
        elapsed_s(ctx.paint_started_at),
    )

def log_completion(ctx: PaintExecutionContext) -> None:
    _logger.info(
        "[EXECUTE] Paint process completed: jobs=%d total_waypoints=%d",
        len(ctx.execution_plan.execution_jobs),
        ctx.paint_total_waypoints,
    )

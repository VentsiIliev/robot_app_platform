from __future__ import annotations

import logging
from time import perf_counter

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState

_logger = logging.getLogger(__name__)


def handle_build_execution_plan(ctx: PaintExecutionContext) -> PaintExecutionState:
    if ctx.should_stop():
        ctx.set_result(False, "Paint process stopped")
        return PaintExecutionState.STOPPED

    service = ctx.production_service
    phase_start = perf_counter()
    try:
        ctx.execution_plan = service._path_preparation_service.build_execution_plan(
            ctx.raw_workpiece,
            skip_debug_plot=not service._path_debug_plots_enabled(),
        )
    except Exception as exc:
        _logger.exception("Paint production plan generation failed")
        ctx.set_result(False, f"Plan generation failed: {exc}")
        return PaintExecutionState.ERROR

    service._log_phase_timing("path_preparation", phase_start, cycle=ctx.cycle_index)
    if ctx.should_stop():
        ctx.set_result(False, "Paint process stopped")
        return PaintExecutionState.STOPPED
    if _path_executor_supports_motion_states(service._path_executor):
        return PaintExecutionState.PICKUP
    return PaintExecutionState.EXECUTE_PAINT


def _path_executor_supports_motion_states(path_executor: object) -> bool:
    if getattr(path_executor, "supports_paint_motion_states", False) is not True:
        return False
    required_methods = (
        "_pickup",
        "_paint_contact",
        "_edge_cleanup",
        "_motion",
        "_paint_process_config",
    )
    return all(hasattr(path_executor, name) for name in required_methods)

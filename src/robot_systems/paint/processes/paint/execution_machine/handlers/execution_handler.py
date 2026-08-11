from __future__ import annotations

from time import perf_counter

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState


def handle_execute_paint(ctx: PaintExecutionContext) -> PaintExecutionState:
    guarded = guard_control(ctx, PaintExecutionState.EXECUTE_PAINT)
    if guarded is not None:
        return guarded

    service = ctx.production_service
    phase_start = perf_counter()
    execute_process = getattr(service._path_executor, "execute_paint_process", None)
    if execute_process is None:
        execute_process = service._path_executor.execute_pickup_and_paint
    try:
        ok, msg = execute_process(ctx.execution_plan, control=ctx.control)
    except TypeError:
        ok, msg = execute_process(ctx.execution_plan)
    service._log_phase_timing("paint_execution", phase_start, success=ok, cycle=ctx.cycle_index)
    if not ok:
        prefix = f"{ctx.workpiece_description}: " if ctx.workpiece_description else ""
        ctx.set_result(False, f"{prefix}{msg}")
        return PaintExecutionState.ERROR

    service._log_phase_timing("run_once_total", ctx.total_started_at, success=True, cycle=ctx.cycle_index)
    prefix = f"{ctx.workpiece_description}: " if ctx.workpiece_description else ""
    ctx.set_result(True, f"{prefix}{msg}")
    return PaintExecutionState.COMPLETED

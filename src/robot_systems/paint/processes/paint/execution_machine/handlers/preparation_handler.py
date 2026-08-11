from __future__ import annotations

from time import perf_counter

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.processes.paint.plan import pick_largest_contour


def handle_prepare_workpiece(ctx: PaintExecutionContext) -> PaintExecutionState:
    if ctx.should_stop():
        ctx.set_result(False, "Paint process stopped")
        return PaintExecutionState.STOPPED
    if ctx.snapshot is None:
        ctx.set_result(False, "Paint capture is not available")
        return PaintExecutionState.ERROR

    ctx.contour = pick_largest_contour(ctx.snapshot.contours)
    if ctx.contour is None:
        ctx.set_result(False, "No usable contour detected")
        return PaintExecutionState.ERROR

    service = ctx.production_service
    phase_start = perf_counter()
    ctx.raw_workpiece, ctx.workpiece_description = service._workpiece_preparation.prepare_workpiece(
        ctx.contour,
        ctx.snapshot.frame,
    )
    service._log_phase_timing("workpiece_preparation", phase_start, cycle=ctx.cycle_index)
    if ctx.should_stop():
        ctx.set_result(False, "Paint process stopped")
        return PaintExecutionState.STOPPED
    return PaintExecutionState.BUILD_EXECUTION_PLAN

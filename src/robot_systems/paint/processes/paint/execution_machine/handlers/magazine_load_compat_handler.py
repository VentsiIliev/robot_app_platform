from __future__ import annotations

from time import perf_counter

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load_handler import (
    supports_fine_magazine_states,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.processes.paint.magazine_load_result import NO_WORKPIECE_AT_MAGAZINE


def handle_magazine_load(ctx: PaintExecutionContext) -> PaintExecutionState:
    """Compatibility handler for simple mocked or legacy magazine services."""
    service = ctx.production_service
    load_service = getattr(service, "_magazine_load_service", None)
    if load_service is None or ctx.magazine_config is None:
        return PaintExecutionState.CAPTURE_WORKPIECE
    if supports_fine_magazine_states(load_service):
        return PaintExecutionState.MAGAZINE_MOVE_TO_MAGAZINE

    guarded = guard_control(ctx, PaintExecutionState.MAGAZINE_LOAD)
    if guarded is not None:
        return guarded

    phase_start = perf_counter()
    ok, msg = load_service.load_to_calibration(ctx.magazine_config, ctx.should_stop)
    service._log_phase_timing("magazine_load", phase_start, success=ok, cycle=ctx.cycle_index)
    if not ok and msg == NO_WORKPIECE_AT_MAGAZINE:
        ctx.set_result(False, msg)
        return PaintExecutionState.COMPLETED
    if not ok:
        ctx.set_result(False, msg)
        return PaintExecutionState.ERROR
    if ctx.should_stop():
        ctx.set_result(False, "Paint process stopped")
        return PaintExecutionState.STOPPED
    return PaintExecutionState.CAPTURE_WORKPIECE

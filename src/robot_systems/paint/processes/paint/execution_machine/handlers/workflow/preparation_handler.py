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
        enable_matching=bool(
            getattr(ctx.process_config, "enable_workpiece_matching", True)
        ),
        default_settings_override=_cycle_default_paint_settings(ctx),
    )
    service._log_phase_timing("workpiece_preparation", phase_start, cycle=ctx.cycle_index)
    if ctx.should_stop():
        ctx.set_result(False, "Paint process stopped")
        return PaintExecutionState.STOPPED
    if ctx.raw_workpiece is None:
        ctx.set_result(False, ctx.workpiece_description or "No matched workpiece")
        return PaintExecutionState.ERROR
    return PaintExecutionState.BUILD_EXECUTION_PLAN


def _cycle_default_paint_settings(ctx: PaintExecutionContext) -> dict | None:
    config = ctx.raw_process_config
    if config is None:
        return None
    return {
        "velocity": float(config.default_paint_velocity_percent),
        "acceleration": float(config.default_paint_acceleration_percent),
        "offset": float(config.default_paint_offset_mm),
    }

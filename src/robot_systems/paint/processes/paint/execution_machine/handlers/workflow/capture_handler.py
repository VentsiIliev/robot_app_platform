from __future__ import annotations

from time import perf_counter

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState


def handle_capture_workpiece(ctx: PaintExecutionContext) -> PaintExecutionState:
    guarded = guard_control(ctx, PaintExecutionState.CAPTURE_WORKPIECE)
    if guarded is not None:
        return guarded

    service = ctx.production_service
    service._restore_brightness_for_capture("before paint capture")
    magazine_enabled = bool(
        ctx.magazine_config is not None and ctx.magazine_config.enabled
    )
    if not magazine_enabled:
        ready, message = service._wait_for_fresh_capture_frame(
            1.0,
            ctx.motion_cancel_requested,
        )
        if not ready:
            if ctx.motion_cancel_requested():
                ctx.set_result(False, "Paint process stopped")
                return PaintExecutionState.STOPPED
            ctx.set_result(False, message)
            return PaintExecutionState.ERROR
    phase_start = perf_counter()
    ctx.snapshot = service._capture_snapshot_service.capture_snapshot(source="paint_process")
    contour_count = len(ctx.snapshot.contours or [])

    service._log_phase_timing(
        "paint_capture",
        phase_start,
        contour_count=contour_count,
        cycle=ctx.cycle_index,
    )
    if ctx.should_stop():
        ctx.set_result(False, "Paint process stopped")
        return PaintExecutionState.STOPPED

    if service._pause_dashboard_live_view_after_capture():
        service._set_dashboard_live_view_paused(
            True,
            image=ctx.snapshot.frame,
            reason="paint capture completed",
        )

    service._freeze_brightness_after_capture()
    return PaintExecutionState.PREPARE_WORKPIECE

from __future__ import annotations

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext


def restore_cycle_resources(
    ctx: PaintExecutionContext,
    *,
    defer_for_next_capture: bool = False,
) -> None:
    if not bool(ctx.result_ok):
        executor = getattr(ctx.production_service, "_path_executor", None)
        plate_service = getattr(executor, "_plate_layout_service", None)
        if plate_service is not None:
            plate_service.cancel()
    if defer_for_next_capture:
        return
    service = ctx.production_service
    service._restore_brightness()
    service._set_dashboard_live_view_paused(False, reason="paint cycle finished")


def stop_machine(ctx: PaintExecutionContext) -> None:
    if ctx.state_machine is not None:
        ctx.state_machine.stop_execution()

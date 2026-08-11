from __future__ import annotations

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_load_handler import (
    supports_fine_magazine_states,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState


def handle_starting(ctx: PaintExecutionContext) -> PaintExecutionState:
    """Choose the first production phase for this cycle."""
    if ctx.should_stop():
        ctx.set_result(False, "Paint process stopped")
        return PaintExecutionState.STOPPED
    if ctx.is_resuming and ctx.resume_state is not None:
        resume_state = ctx.resume_state
        ctx.is_resuming = False
        return resume_state
    service = ctx.production_service
    service._set_dashboard_live_view_paused(False, reason="paint cycle started")
    service._restore_brightness_for_capture("before magazine load")
    if ctx.magazine_config is not None and bool(getattr(ctx.magazine_config, "enabled", False)):
        if supports_fine_magazine_states(getattr(service, "_magazine_load_service", None)):
            return PaintExecutionState.MAGAZINE_MOVE_TO_MAGAZINE
        return PaintExecutionState.MAGAZINE_LOAD
    return PaintExecutionState.CAPTURE_WORKPIECE

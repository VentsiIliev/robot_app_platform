from __future__ import annotations

import logging

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState

_logger = logging.getLogger(__name__)


def handle_paused(ctx: PaintExecutionContext) -> PaintExecutionState:
    _logger.info("[PAINT_EXECUTION] Paused from state %s", getattr(ctx.paused_from_state, "name", None))
    while True:
        if ctx.should_stop():
            ctx.set_result(False, "Paint process stopped")
            return PaintExecutionState.STOPPED
        if ctx.run_allowed.wait(timeout=0.05) and not ctx.control.pause_requested():
            ctx.mark_resuming()
            return PaintExecutionState.STARTING

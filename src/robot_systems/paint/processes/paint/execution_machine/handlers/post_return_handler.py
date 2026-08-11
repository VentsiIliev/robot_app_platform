from __future__ import annotations

import logging
from time import perf_counter

from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.motion_handlers import (
    finish_paint_motion,
    post_return_failure_result,
    set_paint_result,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.timing import timed_block

_logger = logging.getLogger(__name__)


def handle_post_return(ctx: PaintExecutionContext) -> PaintExecutionState:
    executor = ctx.production_service._path_executor
    result_ok = bool(ctx.result_ok)
    result_message = str(ctx.result_message or "")

    with timed_block(_logger, "return_after_paint_process"):
        if executor._post_execute_callback is None:
            _logger.info("[EXECUTE] Post-execute return skipped: callback not configured")
        else:
            try:
                return_started = perf_counter()
                moved = bool(executor._post_execute_callback())
            except Exception:
                _logger.exception("[EXECUTE] Post-execute callback failed")
                _logger.info(
                    "[TIMING] paint_process success=false stage=post_return total_elapsed_s=%.3f",
                    elapsed_s(ctx.paint_started_at),
                )
                result_ok, result_message = post_return_failure_result(result_ok, result_message)
            else:
                if not moved:
                    _logger.info(
                        "[TIMING] paint_process success=false stage=post_return return_elapsed_s=%.3f total_elapsed_s=%.3f",
                        elapsed_s(return_started),
                        elapsed_s(ctx.paint_started_at),
                    )
                    result_ok, result_message = post_return_failure_result(result_ok, result_message)

    set_paint_result(ctx, result_ok, result_message, already_prefixed=True)
    finish_paint_motion(ctx, success=result_ok)
    return PaintExecutionState.COMPLETED if result_ok else PaintExecutionState.ERROR

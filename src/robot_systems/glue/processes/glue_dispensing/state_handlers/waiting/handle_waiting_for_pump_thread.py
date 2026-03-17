from __future__ import annotations
import logging
import time

from src.robot_systems.glue.processes.glue_dispensing.dispensing_error import (
    DispensingErrorCode,
    DispensingErrorKind,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)

def handle_waiting_for_pump_thread(context) -> GlueDispensingState:
    S = GlueDispensingState
    pump_thread = context.pump_thread
    path_index = context.current_path_index

    try:
        while pump_thread.is_alive():
            next_state = context.pump_thread_ops.handle_interruption(
                pump_thread,
                paused_state=S.WAITING_FOR_PUMP_THREAD,
            )
            if next_state is not None:
                return next_state

            time.sleep(context.pump_thread_wait_poll_s)

        thread_error = context.pump_thread_ops.get_failure_exception(pump_thread)
        context.pump_thread_ops.capture_progress(pump_thread)
        context.pump_thread_ops.clear()
        if thread_error is not None:
            return context.fail(
                kind=DispensingErrorKind.THREAD,
                code=DispensingErrorCode.PUMP_THREAD_EXECUTION_FAILED,
                state=S.WAITING_FOR_PUMP_THREAD,
                operation="pump_thread_execution",
                message=f"Pump thread failed on path {path_index}",
                exc=thread_error,
            )
        _logger.debug("Pump thread completed for path %s", path_index)
        return S.TURNING_OFF_PUMP

    except Exception as exc:
        context.pump_thread_ops.clear()
        return context.fail(
            kind=DispensingErrorKind.THREAD,
            code=DispensingErrorCode.PUMP_THREAD_WAIT_FAILED,
            state=S.WAITING_FOR_PUMP_THREAD,
            operation="wait_for_pump_thread",
            message=f"Error waiting for pump thread on path {path_index}",
            exc=exc,
        )

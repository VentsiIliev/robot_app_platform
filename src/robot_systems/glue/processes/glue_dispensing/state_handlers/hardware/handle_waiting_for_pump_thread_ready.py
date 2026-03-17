from __future__ import annotations

from src.robot_systems.glue.processes.glue_dispensing.dispensing_error import (
    DispensingErrorCode,
    DispensingErrorKind,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState


def handle_waiting_for_pump_thread_ready(context) -> GlueDispensingState:
    S = GlueDispensingState

    if context.pump_thread is None:
        return S.SENDING_PATH_POINTS

    if context.pump_ready_event is None:
        return context.fail(
            kind=DispensingErrorKind.THREAD,
            code=DispensingErrorCode.PUMP_THREAD_READY_MISSING,
            state=S.WAITING_FOR_PUMP_THREAD_READY,
            operation="wait_for_pump_ready",
            message="Pump adjustment thread missing ready event",
        )

    if not context.pump_ready_event.wait(timeout=context.pump_ready_timeout_s):
        return context.fail(
            kind=DispensingErrorKind.TIMEOUT,
            code=DispensingErrorCode.PUMP_THREAD_READY_TIMEOUT,
            state=S.WAITING_FOR_PUMP_THREAD_READY,
            operation="wait_for_pump_ready",
            message="Pump adjustment thread failed to become ready within 5 s",
        )

    return S.SENDING_PATH_POINTS

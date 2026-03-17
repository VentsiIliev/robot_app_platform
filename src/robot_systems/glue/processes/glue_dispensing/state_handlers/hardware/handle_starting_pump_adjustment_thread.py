from __future__ import annotations
import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_error import (
    DispensingErrorCode,
    DispensingErrorKind,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_starting_pump_adjustment_thread(
    context,
    adjust_pump_speed: bool = True,
) -> GlueDispensingState:
    S = GlueDispensingState

    context.pump_thread_ops.clear()
    context.pump_thread_ops.create_ready_event()

    if adjust_pump_speed and context.spray_on and context.motor_service is not None:
        motor_address = context.get_valid_motor_address_for_current_path()
        if motor_address is None:
            _logger.warning("Invalid motor address — skipping dynamic pump adjustment")
        else:
            settings = context.get_segment_settings()
            threshold = float(settings.reach_end_threshold) if settings else 1.0
            try:
                context.pump_thread_ops.start_for_current_path(
                    motor_address=motor_address,
                    reach_end_threshold=threshold,
                )
            except Exception as exc:
                return context.fail(
                    kind=DispensingErrorKind.THREAD,
                    code=DispensingErrorCode.PUMP_THREAD_START_FAILED,
                    state=S.STARTING_PUMP_ADJUSTMENT_THREAD,
                    operation="start_pump_adjustment_thread",
                    message="Failed to start pump adjustment thread",
                    exc=exc,
                )
            return S.WAITING_FOR_PUMP_THREAD_READY

    return S.SENDING_PATH_POINTS

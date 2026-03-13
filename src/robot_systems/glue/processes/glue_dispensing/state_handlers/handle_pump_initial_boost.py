from __future__ import annotations
import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_pump_initial_boost(context) -> GlueDispensingState:
    S = GlueDispensingState

    if context.stop_event.is_set():
        return S.STOPPED

    if not context.run_allowed.is_set():
        context.paused_from_state = S.PUMP_INITIAL_BOOST
        return S.PAUSED

    if not context.spray_on or context.motor_started:
        return S.STARTING_PUMP_ADJUSTMENT_THREAD

    motor_address = context.get_motor_address_for_current_path()
    if motor_address == -1:
        _logger.error("Invalid motor address for path %s", context.current_path_index)
        return S.ERROR

    success = context.pump_controller.pump_on(motor_address, context.current_settings)
    if not success:
        _logger.error("pump_on failed for motor_address=%s", motor_address)
        return S.ERROR

    context.motor_started = True
    _logger.debug("Pump started at motor_address=%s", motor_address)
    return S.STARTING_PUMP_ADJUSTMENT_THREAD


from __future__ import annotations
import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_transition_between_paths(
    context,
    turn_off_pump: bool = True,
) -> GlueDispensingState:
    S = GlueDispensingState

    if context.stop_event.is_set():
        return S.STOPPED

    if not context.run_allowed.is_set():
        context.paused_from_state = S.TRANSITION_BETWEEN_PATHS
        return S.PAUSED

    if turn_off_pump and context.motor_started and context.spray_on:
        motor_address = context.get_motor_address_for_current_path()
        if motor_address == -1:
            _logger.error("Invalid motor address during path transition")
            return S.ERROR
        context.pump_controller.pump_off(motor_address, context.current_settings)
        context.motor_started = False
        _logger.debug("Pump stopped between paths")

    context.current_path_index += 1
    context.current_point_index = 0

    if context.current_path_index >= len(context.paths):
        _logger.debug("All paths completed")
        return S.COMPLETED

    _logger.debug("Transitioning to path %s", context.current_path_index)
    return S.STARTING


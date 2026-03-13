from __future__ import annotations
import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_executing_path(context) -> GlueDispensingState:
    S = GlueDispensingState

    if context.stop_event.is_set():
        return S.STOPPED

    if not context.run_allowed.is_set():
        context.paused_from_state = S.EXECUTING_PATH
        return S.PAUSED

    if context.spray_on and not context.generator_started and context.generator is not None:
        try:
            context.generator.turn_on()
            context.generator_started = True
            _logger.debug("Generator started for path %s", context.current_path_index)
        except Exception:
            _logger.exception("Failed to start generator")
            return S.ERROR

    return S.PUMP_INITIAL_BOOST


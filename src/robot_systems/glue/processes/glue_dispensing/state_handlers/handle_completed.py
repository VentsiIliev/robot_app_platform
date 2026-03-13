from __future__ import annotations
import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_completed(context) -> GlueDispensingState:
    _logger.info("Glue dispensing completed successfully")

    if context.motor_started and context.spray_on and context.pump_controller:
        motor_address = context.get_motor_address_for_current_path()
        if motor_address != -1:
            try:
                context.pump_controller.pump_off(motor_address, context.current_settings)
            except Exception:
                _logger.exception("pump_off failed in COMPLETED handler")
        context.motor_started = False

    if context.generator_started and context.generator is not None:
        try:
            context.generator.turn_off()
        except Exception:
            _logger.exception("generator turn_off failed in COMPLETED handler")
        context.generator_started = False

    context.operation_just_completed = True
    return GlueDispensingState.IDLE


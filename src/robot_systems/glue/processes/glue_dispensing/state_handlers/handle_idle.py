import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_idle(context) -> GlueDispensingState:
    _logger.debug("Machine reached IDLE — stopping execution")
    if context.state_machine is not None:
        context.state_machine.stop_execution()
    return GlueDispensingState.IDLE


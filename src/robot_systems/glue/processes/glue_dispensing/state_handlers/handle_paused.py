from __future__ import annotations
import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_paused(context) -> GlueDispensingState:
    S = GlueDispensingState
    _logger.debug("Entering PAUSED state (paused_from=%s)", context.paused_from_state)

    while True:
        if context.stop_event.is_set():
            _logger.debug("Stop requested while paused")
            return S.STOPPED

        if context.run_allowed.wait(timeout=0.05):
            _logger.debug("Resuming from PAUSED → STARTING")
            return S.STARTING


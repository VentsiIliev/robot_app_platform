from __future__ import annotations

import logging

from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_idle(context) -> GlueDispensingState:
    _logger.debug("Machine reached IDLE — stopping execution")
    if context.state_machine is not None:
        context.state_machine.stop_execution()
    return GlueDispensingState.IDLE


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


def handle_stopped(context) -> GlueDispensingState:
    _logger.info("Handling STOPPED state — cleaning up hardware")
    context.cleanup.shutdown_best_effort()
    return GlueDispensingState.IDLE


def handle_completed(context) -> GlueDispensingState:
    _logger.info("Glue dispensing completed successfully")
    context.cleanup.stop_pump_if_running()
    return GlueDispensingState.TURNING_OFF_GENERATOR


def handle_error(context) -> GlueDispensingState:
    if context.last_error is not None:
        _logger.error(
            "Glue dispensing in ERROR state after %s [state=%s path=%s point=%s]",
            context.last_error.operation,
            context.last_error.state.name,
            context.last_error.path_index,
            context.last_error.point_index,
        )
    else:
        _logger.error("Glue dispensing in ERROR state — stopping hardware")
    context.cleanup.shutdown_best_effort()
    return GlueDispensingState.IDLE

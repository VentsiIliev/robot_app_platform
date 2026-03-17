from __future__ import annotations

import logging

from src.robot_systems.glue.processes.glue_dispensing.dispensing_error import (
    DispensingErrorCode,
    DispensingErrorKind,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_turning_on_generator(context) -> GlueDispensingState:
    S = GlueDispensingState

    if context.spray_on and not context.generator_started and context.generator is not None:
        try:
            context.generator.turn_on()
            context.generator_started = True
            _logger.debug("Generator started for path %s", context.current_path_index)
        except Exception as exc:
            return context.fail(
                kind=DispensingErrorKind.GENERATOR,
                code=DispensingErrorCode.GENERATOR_START_FAILED,
                state=S.TURNING_ON_GENERATOR,
                operation="turn_on_generator",
                message="Failed to start generator",
                exc=exc,
            )

    return S.TURNING_ON_PUMP


def handle_turning_off_generator(context) -> GlueDispensingState:
    if context.generator_started and context.generator is not None:
        try:
            context.generator.turn_off()
        except Exception as exc:
            return context.fail(
                kind=DispensingErrorKind.GENERATOR,
                code=DispensingErrorCode.GENERATOR_STOP_FAILED,
                state=GlueDispensingState.TURNING_OFF_GENERATOR,
                operation="turn_off_generator",
                message="generator turn_off failed in TURNING_OFF_GENERATOR handler",
                exc=exc,
            )
        context.mark_generator_stopped()

    context.mark_completed()
    return GlueDispensingState.IDLE

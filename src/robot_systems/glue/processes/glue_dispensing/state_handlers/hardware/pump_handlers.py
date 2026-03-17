from __future__ import annotations

import logging

from src.robot_systems.glue.processes.glue_dispensing.dispensing_error import (
    DispensingErrorCode,
    DispensingErrorKind,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def _get_pump_controller_exception(context):
    getter = getattr(context.pump_controller, "get_last_exception", None)
    if getter is None:
        return None
    exc = getter()
    if isinstance(exc, Exception):
        return exc
    return None


def handle_turning_on_pump(context) -> GlueDispensingState:
    S = GlueDispensingState

    if not context.spray_on or context.motor_started:
        return S.STARTING_PUMP_ADJUSTMENT_THREAD

    motor_address = context.get_valid_motor_address_for_current_path()
    if motor_address is None:
        return context.fail(
            kind=DispensingErrorKind.CONFIG,
            code=DispensingErrorCode.INVALID_MOTOR_ADDRESS,
            state=S.TURNING_ON_PUMP,
            operation="resolve_motor_address",
            message="Invalid motor address for current path",
        )

    success = context.pump_controller.pump_on(motor_address, context.current_settings)
    if not success:
        return context.fail(
            kind=DispensingErrorKind.PUMP,
            code=DispensingErrorCode.PUMP_ON_FAILED,
            state=S.TURNING_ON_PUMP,
            operation="pump_on",
            message=f"pump_on failed for motor_address={motor_address}",
            exc=_get_pump_controller_exception(context),
        )

    context.motor_started = True
    _logger.debug("Pump started at motor_address=%s", motor_address)
    return S.STARTING_PUMP_ADJUSTMENT_THREAD


def handle_turning_off_pump(
    context,
    turn_off_pump: bool = True,
) -> GlueDispensingState:
    S = GlueDispensingState

    if turn_off_pump and context.motor_started and context.spray_on:
        motor_address = context.get_valid_motor_address_for_current_path()
        if motor_address is None:
            return context.fail(
                kind=DispensingErrorKind.CONFIG,
                code=DispensingErrorCode.INVALID_MOTOR_ADDRESS,
                state=S.TURNING_OFF_PUMP,
                operation="resolve_motor_address",
                message="Invalid motor address during path transition",
            )
        success = context.pump_controller.pump_off(motor_address, context.current_settings)
        if not success:
            return context.fail(
                kind=DispensingErrorKind.PUMP,
                code=DispensingErrorCode.PUMP_OFF_FAILED,
                state=S.TURNING_OFF_PUMP,
                operation="pump_off",
                message=f"pump_off failed for motor_address={motor_address}",
                exc=_get_pump_controller_exception(context),
            )
        context.mark_motor_stopped()
        _logger.debug("Pump stopped between paths")

    return S.ADVANCING_PATH

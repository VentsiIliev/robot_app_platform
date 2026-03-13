from __future__ import annotations
import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)

_EXECUTION_STATES = frozenset({
    GlueDispensingState.EXECUTING_PATH,
    GlueDispensingState.PUMP_INITIAL_BOOST,
    GlueDispensingState.STARTING_PUMP_ADJUSTMENT_THREAD,
    GlueDispensingState.SENDING_PATH_POINTS,
    GlueDispensingState.WAIT_FOR_PATH_COMPLETION,
})


def handle_starting(context) -> GlueDispensingState:
    S = GlueDispensingState

    if context.stop_event.is_set():
        return S.STOPPED

    if not context.run_allowed.is_set():
        context.paused_from_state = S.STARTING
        return S.PAUSED

    if context.is_resuming and context.has_valid_context():
        context.is_resuming = False
        return _handle_resume(context)

    if context.current_path_index >= len(context.paths):
        return S.COMPLETED

    path, settings = context.paths[context.current_path_index]

    if not path:
        _logger.debug("Empty path at index %s, skipping", context.current_path_index)
        context.current_path_index += 1
        context.current_point_index = 0
        return S.STARTING

    context.current_path = path
    context.current_settings = settings
    context.current_point_index = 0

    if not _move_to_first_point(context, path[0]):
        _logger.error("Failed to initiate move to first point for path %s", context.current_path_index)
        return S.ERROR

    return S.MOVING_TO_FIRST_POINT


def _handle_resume(context) -> GlueDispensingState:
    S = GlueDispensingState

    if context.current_path_index >= len(context.paths):
        return S.COMPLETED

    path, settings = context.paths[context.current_path_index]
    paused_from = context.paused_from_state

    if paused_from in (S.TRANSITION_BETWEEN_PATHS, S.MOVING_TO_FIRST_POINT):
        context.current_path = path
        context.current_settings = settings
        context.current_point_index = 0
        return S.MOVING_TO_FIRST_POINT if _move_to_first_point(context, path[0]) else S.ERROR

    if paused_from in _EXECUTION_STATES:
        if context.current_point_index >= len(path):
            context.current_path_index += 1
            context.current_point_index = 0
            return S.STARTING
        context.current_path = path[context.current_point_index:]
        context.current_settings = settings
        return S.EXECUTING_PATH

    # Fallback: restart path from beginning
    context.current_path = path
    context.current_settings = settings
    context.current_point_index = 0
    return S.MOVING_TO_FIRST_POINT if _move_to_first_point(context, path[0]) else S.ERROR


def _move_to_first_point(context, target) -> bool:
    try:
        return context.robot_service.move_ptp(
            position=target,
            tool=context.robot_tool,
            user=context.robot_user,
            velocity=context.global_velocity,
            acceleration=context.global_acceleration,
            wait_to_reach=False,
        )
    except Exception:
        _logger.exception("move_ptp to first point failed")
        return False


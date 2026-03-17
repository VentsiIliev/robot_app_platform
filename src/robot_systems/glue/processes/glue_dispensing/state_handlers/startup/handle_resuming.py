from __future__ import annotations

from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_EXECUTION_STATES = frozenset({
    GlueDispensingState.TURNING_ON_GENERATOR,
    GlueDispensingState.TURNING_ON_PUMP,
    GlueDispensingState.STARTING_PUMP_ADJUSTMENT_THREAD,
    GlueDispensingState.WAITING_FOR_PUMP_THREAD_READY,
    GlueDispensingState.SENDING_PATH_POINTS,
    GlueDispensingState.ROUTING_PATH_COMPLETION_WAIT,
    GlueDispensingState.WAITING_FOR_PUMP_THREAD,
    GlueDispensingState.WAITING_FOR_FINAL_POSITION,
})


def handle_resuming(context) -> GlueDispensingState:
    S = GlueDispensingState

    if not context.path_ops.has_remaining_paths():
        return S.COMPLETED

    entry = context.path_ops.get_current_path_entry()
    paused_from = context.paused_from_state

    if paused_from in (S.ADVANCING_PATH, S.TURNING_OFF_PUMP, S.MOVING_TO_FIRST_POINT):
        context.path_ops.restart_current_path()
        return S.ISSUING_MOVE_TO_FIRST_POINT

    if paused_from == S.WAITING_FOR_FINAL_POSITION:
        if context.segment_trajectory_submitted and not context.segment_trajectory_completed:
            context.path_ops.resume_current_path_from_progress()
            return S.TURNING_ON_GENERATOR
        if context.segment_trajectory_completed:
            return S.TURNING_OFF_PUMP

    if paused_from in _EXECUTION_STATES:
        if context.current_point_index >= len(entry.points):
            context.path_ops.advance_to_next_path()
            return S.STARTING
        context.path_ops.resume_current_path_from_progress()
        return S.TURNING_ON_GENERATOR

    context.path_ops.restart_current_path()
    return S.ISSUING_MOVE_TO_FIRST_POINT

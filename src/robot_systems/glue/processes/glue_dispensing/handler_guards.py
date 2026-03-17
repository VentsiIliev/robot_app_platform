from __future__ import annotations

from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState


def guard_stop(context) -> GlueDispensingState | None:
    if context.stop_event.is_set():
        return GlueDispensingState.STOPPED
    return None


def guard_pause(
    context,
    current_state: GlueDispensingState,
) -> GlueDispensingState | None:
    if not context.run_allowed.is_set():
        context.paused_from_state = current_state
        return GlueDispensingState.PAUSED
    return None

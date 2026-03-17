from __future__ import annotations

from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState


def handle_loading_current_path(context) -> GlueDispensingState:
    context.path_ops.restart_current_path()
    return GlueDispensingState.ISSUING_MOVE_TO_FIRST_POINT

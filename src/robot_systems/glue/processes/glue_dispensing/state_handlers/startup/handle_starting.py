from __future__ import annotations
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState


def handle_starting(context) -> GlueDispensingState:
    S = GlueDispensingState

    if context.is_resuming and context.has_valid_context():
        context.is_resuming = False
        return S.RESUMING

    return S.LOADING_PATH

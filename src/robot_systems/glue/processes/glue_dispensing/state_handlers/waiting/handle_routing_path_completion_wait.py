from __future__ import annotations

from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState


def handle_routing_path_completion_wait(context) -> GlueDispensingState:
    S = GlueDispensingState

    if context.pump_thread is not None:
        return S.WAITING_FOR_PUMP_THREAD
    return S.WAITING_FOR_FINAL_POSITION

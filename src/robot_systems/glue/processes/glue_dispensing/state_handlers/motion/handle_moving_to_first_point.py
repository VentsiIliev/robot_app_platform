from __future__ import annotations
import time
from src.robot_systems.glue.processes.glue_dispensing.dispensing_error import (
    DispensingErrorCode,
    DispensingErrorKind,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState


def handle_moving_to_first_point(context) -> GlueDispensingState:
    S = GlueDispensingState

    if not context.path_ops.has_current_path_loaded():
        return context.fail(
            kind=DispensingErrorKind.STATE,
            code=DispensingErrorCode.MISSING_CURRENT_PATH,
            state=S.MOVING_TO_FIRST_POINT,
            operation="validate_current_path",
            message="No current_settings or current_path in MOVING_TO_FIRST_POINT",
        )

    threshold = context.motion_ops.get_reach_start_threshold()
    deadline = time.monotonic() + context.move_to_first_point_timeout_s

    while True:
        if context.stop_event.is_set():
            return S.STOPPED

        if not context.run_allowed.is_set():
            context.pause_from(S.MOVING_TO_FIRST_POINT)
            return S.PAUSED

        if context.motion_ops.is_at_current_path_start(threshold):
            context.path_ops.mark_first_point_reached()
            return S.TURNING_ON_GENERATOR

        if time.monotonic() > deadline:
            return context.fail(
                kind=DispensingErrorKind.TIMEOUT,
                code=DispensingErrorCode.MOVE_TO_FIRST_POINT_TIMEOUT,
                state=S.MOVING_TO_FIRST_POINT,
                operation="wait_for_first_point",
                message=f"Timeout waiting to reach first point of path {context.current_path_index}",
            )

        time.sleep(context.move_to_first_point_poll_s)

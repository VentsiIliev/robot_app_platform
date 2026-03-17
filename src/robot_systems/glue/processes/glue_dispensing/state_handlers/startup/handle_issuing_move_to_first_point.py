from __future__ import annotations

from src.robot_systems.glue.processes.glue_dispensing.dispensing_error import (
    DispensingErrorCode,
    DispensingErrorKind,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState


def handle_issuing_move_to_first_point(context) -> GlueDispensingState:
    S = GlueDispensingState

    target = context.path_ops.get_current_path_start_point()
    try:
        ok = context.robot_service.move_ptp(
            position=target,
            tool=context.robot_tool,
            user=context.robot_user,
            velocity=context.global_velocity,
            acceleration=context.global_acceleration,
            wait_to_reach=False,
        )
    except Exception as exc:
        return context.fail(
            kind=DispensingErrorKind.MOTION,
            code=DispensingErrorCode.MOVE_TO_FIRST_POINT_FAILED,
            state=S.ISSUING_MOVE_TO_FIRST_POINT,
            operation="move_ptp_to_first_point",
            message="move_ptp to first point failed",
            exc=exc,
        )

    if not ok:
        if context.stop_event.is_set():
            return S.STOPPED
        if not context.run_allowed.is_set():
            context.pause_from(S.ISSUING_MOVE_TO_FIRST_POINT)
            return S.PAUSED
        return context.fail(
            kind=DispensingErrorKind.MOTION,
            code=DispensingErrorCode.MOVE_TO_FIRST_POINT_FAILED,
            state=S.ISSUING_MOVE_TO_FIRST_POINT,
            operation="move_ptp_to_first_point",
            message="Failed to initiate move to first point",
        )

    return S.MOVING_TO_FIRST_POINT

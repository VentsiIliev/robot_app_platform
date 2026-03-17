from __future__ import annotations
import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_error import (
    DispensingErrorCode,
    DispensingErrorKind,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_sending_path_points(context) -> GlueDispensingState:
    S = GlueDispensingState

    path = context.current_path
    path_index = context.current_path_index
    start = context.current_point_index
    segment_path = list(path[start:])

    if not segment_path:
        _logger.debug("No remaining trajectory points to send for path %s", path_index)
        return S.ROUTING_PATH_COMPLETION_WAIT

    if context.stop_event.is_set():
        context.stop_with_progress(path_index, start)
        return S.STOPPED

    if not context.run_allowed.is_set():
        context.pause_with_progress(S.SENDING_PATH_POINTS, path_index, start)
        return S.PAUSED

    first_point = segment_path[0]
    rx = float(first_point[3]) if len(first_point) > 3 else 180.0
    ry = float(first_point[4]) if len(first_point) > 4 else 0.0
    rz = float(first_point[5]) if len(first_point) > 5 else 0.0

    try:
        ok = context.robot_service.execute_trajectory(
            path=segment_path,
            rx=rx,
            ry=ry,
            rz=rz,
            vel=context.global_velocity,
            acc=context.global_acceleration,
            blocking=False,
        )
    except Exception as exc:
        context.stop_with_progress(path_index, start)
        return context.fail(
            kind=DispensingErrorKind.MOTION,
            code=DispensingErrorCode.EXECUTE_TRAJECTORY_FAILED,
            state=S.SENDING_PATH_POINTS,
            operation="execute_trajectory",
            message=f"Exception executing trajectory for path {path_index} from point {start}",
            exc=exc,
        )

    if ok is False:
        context.stop_with_progress(path_index, start)
        return context.fail(
            kind=DispensingErrorKind.MOTION,
            code=DispensingErrorCode.EXECUTE_TRAJECTORY_FAILED,
            state=S.SENDING_PATH_POINTS,
            operation="execute_trajectory",
            message=f"execute_trajectory failed for path {path_index} from point {start}",
        )

    command_info = context.robot_service.get_last_trajectory_command_info()
    task_id = None
    if isinstance(command_info, dict):
        task_id = command_info.get("task_id")

    context.mark_segment_trajectory_submitted(start, task_id=task_id)

    _logger.debug(
        "Submitted trajectory for path %s from point %s with %s waypoints",
        path_index,
        start,
        len(segment_path),
    )
    return S.ROUTING_PATH_COMPLETION_WAIT

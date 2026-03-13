from __future__ import annotations
import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

_logger = logging.getLogger(__name__)


def handle_sending_path_points(context) -> GlueDispensingState:
    S = GlueDispensingState

    path = context.current_path
    path_index = context.current_path_index
    start = context.current_point_index

    for i, point in enumerate(path, start=start):
        if context.stop_event.is_set():
            context.save_progress(path_index, i)
            return S.STOPPED

        if not context.run_allowed.is_set():
            context.save_progress(path_index, i)
            context.paused_from_state = S.SENDING_PATH_POINTS
            return S.PAUSED

        try:
            ok = context.robot_service.move_linear(
                position=point,
                tool=context.robot_tool,
                user=context.robot_user,
                velocity=context.global_velocity,
                acceleration=context.global_acceleration,
                blendR=1.0,
                wait_to_reach=False,
            )
        except Exception:
            _logger.exception("Exception sending point %s of path %s", i, path_index)
            context.save_progress(path_index, i)
            return S.ERROR

        if not ok:
            _logger.error("move_linear failed at point %s of path %s", i, path_index)
            context.save_progress(path_index, i)
            return S.ERROR

    _logger.debug("All %s points sent for path %s", len(path), path_index)
    return S.WAIT_FOR_PATH_COMPLETION


from __future__ import annotations
import math
import time

from src.robot_systems.glue.processes.glue_dispensing.dispensing_error import (
    DispensingErrorCode,
    DispensingErrorKind,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState


def _dist(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])))


def handle_waiting_for_final_position(context) -> GlueDispensingState:
    S = GlueDispensingState

    if not context.current_path:
        return S.TURNING_OFF_PUMP

    final_point = context.path_ops.get_current_path_end_point()
    settings = context.get_segment_settings()
    threshold = float(settings.reach_end_threshold) if settings else 1.0

    while True:
        if context.stop_event.is_set():
            context.stop_current_segment_execution()
            return S.STOPPED

        if not context.run_allowed.is_set():
            context.pause_current_segment_execution(S.WAITING_FOR_FINAL_POSITION)
            return S.PAUSED

        status = context.robot_service.get_execution_status()
        if isinstance(status, dict):
            task_id = context.current_segment_task_id
            last_completed_task_id = status.get("last_completed_task_id")
            last_completed_result = status.get("last_completed_result")
            if task_id is not None and last_completed_task_id == task_id:
                if last_completed_result not in (None, 0):
                    return context.fail(
                        kind=DispensingErrorKind.MOTION,
                        code=DispensingErrorCode.EXECUTE_TRAJECTORY_FAILED,
                        state=S.WAITING_FOR_FINAL_POSITION,
                        operation="wait_for_trajectory_completion",
                        message=(
                            f"trajectory task {task_id} failed with result "
                            f"{last_completed_result}"
                        ),
                    )
            is_executing = bool(status.get("is_executing", False))
            queue_size = int(status.get("queue_size", 0) or 0)
            if is_executing or queue_size > 0:
                time.sleep(context.final_position_poll_s)
                continue

        pos = context.robot_service.get_current_position()
        if pos and _dist(pos, final_point) < threshold:
            context.mark_segment_trajectory_completed()
            return S.TURNING_OFF_PUMP

        time.sleep(context.final_position_poll_s)

from __future__ import annotations
import math
import time
import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState
from src.robot_systems.glue.settings.glue import GlueSettingKey

_logger = logging.getLogger(__name__)
_POLL_S = 0.02
_TIMEOUT_S = 30.0

def _dist(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])))


def handle_moving_to_first_point(context) -> GlueDispensingState:
    S = GlueDispensingState

    if not context.current_settings or not context.current_path:
        _logger.error("No current_settings or current_path in MOVING_TO_FIRST_POINT")
        return S.ERROR

    threshold = float(context.current_settings.get(GlueSettingKey.REACH_START_THRESHOLD.value, 1.0))
    target = context.current_path[0]
    deadline = time.monotonic() + _TIMEOUT_S

    while True:
        if context.stop_event.is_set():
            return S.STOPPED

        if not context.run_allowed.is_set():
            context.paused_from_state = S.MOVING_TO_FIRST_POINT
            return S.PAUSED

        pos = context.robot_service.get_current_position()
        if pos and _dist(pos, target) < threshold:
            context.current_point_index = 0
            _logger.debug("Reached first point of path %s", context.current_path_index)
            return S.EXECUTING_PATH

        if time.monotonic() > deadline:
            _logger.error("Timeout waiting to reach first point of path %s", context.current_path_index)
            return S.ERROR

        time.sleep(_POLL_S)


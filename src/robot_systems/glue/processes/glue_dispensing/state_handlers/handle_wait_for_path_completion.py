from __future__ import annotations
import math
import time
import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState
from src.robot_systems.glue.settings.glue import GlueSettingKey

_logger = logging.getLogger(__name__)
_POLL_S = 0.1


def handle_wait_for_path_completion(context) -> GlueDispensingState:
    pump_thread = context.pump_thread
    if pump_thread is not None:
        return _wait_via_pump_thread(context, pump_thread)
    return _wait_via_position_poll(context)


# ── pump-thread path ───────────────────────────────────────────────────────────

def _wait_via_pump_thread(context, pump_thread) -> GlueDispensingState:
    S = GlueDispensingState
    path_index = context.current_path_index
    try:
        while pump_thread.is_alive():
            if context.stop_event.is_set():
                pump_thread.join(timeout=2.0)
                _capture_pump_progress(context, pump_thread)
                context.pump_thread = None
                return S.STOPPED

            if not context.run_allowed.is_set():
                pump_thread.join(timeout=2.0)
                _capture_pump_progress(context, pump_thread)
                context.paused_from_state = S.WAIT_FOR_PATH_COMPLETION
                context.pump_thread = None
                return S.PAUSED

            time.sleep(_POLL_S)

        _capture_pump_progress(context, pump_thread)
        context.pump_thread = None
        _logger.debug("Pump thread completed for path %s", path_index)
        return S.TRANSITION_BETWEEN_PATHS

    except Exception:
        _logger.exception("Error waiting for pump thread on path %s", path_index)
        context.pump_thread = None
        return S.ERROR


def _capture_pump_progress(context, pump_thread) -> None:
    try:
        if hasattr(pump_thread, "result") and pump_thread.result is not None:
            result = pump_thread.result
            if len(result) >= 2:
                context.current_point_index = result[1]
    except Exception:
        _logger.warning("Could not capture pump thread progress")


# ── position-poll fallback (spray_on=False or no pump adj) ────────────────────

def _dist(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])))


def _wait_via_position_poll(context) -> GlueDispensingState:
    S = GlueDispensingState

    if not context.current_path:
        return S.TRANSITION_BETWEEN_PATHS

    final_point = context.current_path[-1]
    threshold = float(
        context.current_settings.get(GlueSettingKey.REACH_END_THRESHOLD.value, 1.0)
        if context.current_settings else 1.0
    )

    while True:
        if context.stop_event.is_set():
            return S.STOPPED

        if not context.run_allowed.is_set():
            context.paused_from_state = S.WAIT_FOR_PATH_COMPLETION
            return S.PAUSED

        pos = context.robot_service.get_current_position()
        if pos and _dist(pos, final_point) < threshold:
            return S.TRANSITION_BETWEEN_PATHS

        time.sleep(_POLL_S)


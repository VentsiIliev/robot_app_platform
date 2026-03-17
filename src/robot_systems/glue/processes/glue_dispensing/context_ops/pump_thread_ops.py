from __future__ import annotations

import logging
import threading

_logger = logging.getLogger(__name__)


class DispensingPumpThreadOps:
    def __init__(self, context) -> None:
        self._context = context

    def clear(self) -> None:
        self._context.pump_thread = None

    def create_ready_event(self) -> None:
        self._context.pump_ready_event = threading.Event()

    def start_for_current_path(self, motor_address: int, reach_end_threshold: float) -> None:
        from src.robot_systems.glue.processes.glue_dispensing.pump_speed_adjuster import (
            start_pump_speed_adjustment_thread,
        )

        context = self._context
        settings = context.get_segment_settings()
        context.pump_thread = start_pump_speed_adjustment_thread(
            motor_service=context.motor_service,
            robot_service=context.robot_service,
            settings=settings,
            motor_address=motor_address,
            path=context.current_path,
            reach_end_threshold=reach_end_threshold,
            pump_ready_event=context.pump_ready_event,
            start_point_index=context.current_point_index,
            context=context,
        )

    def capture_progress(self, pump_thread) -> None:
        context = self._context
        try:
            if hasattr(pump_thread, "result") and pump_thread.result is not None:
                result = pump_thread.result
                if len(result) >= 2:
                    context.current_point_index = result[1]
        except Exception:
            _logger.warning("Could not capture pump thread progress")

    def get_failure_exception(self, pump_thread):
        result = getattr(pump_thread, "result", None)
        if not isinstance(result, tuple) or len(result) < 3:
            return None
        exc = result[2]
        if isinstance(exc, Exception):
            return exc
        return None

    def handle_interruption(self, pump_thread, paused_state):
        from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

        context = self._context

        if context.stop_event.is_set():
            pump_thread.join(timeout=context.pump_thread_join_timeout_s)
            self.capture_progress(pump_thread)
            self.clear()
            return GlueDispensingState.STOPPED

        if not context.run_allowed.is_set():
            pump_thread.join(timeout=context.pump_thread_join_timeout_s)
            self.capture_progress(pump_thread)
            context.pause_from(paused_state)
            self.clear()
            return GlueDispensingState.PAUSED

        return None

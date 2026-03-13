from __future__ import annotations
import threading
import logging
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState
from src.robot_systems.glue.settings.glue import GlueSettingKey
from src.robot_systems.glue.processes.glue_dispensing.pump_speed_adjuster import start_pump_speed_adjustment_thread

_logger = logging.getLogger(__name__)


def handle_starting_pump_adjustment_thread(
    context,
    adjust_pump_speed: bool = True,
) -> GlueDispensingState:
    S = GlueDispensingState

    if context.stop_event.is_set():
        return S.STOPPED

    if not context.run_allowed.is_set():
        context.paused_from_state = S.STARTING_PUMP_ADJUSTMENT_THREAD
        return S.PAUSED

    context.pump_thread = None
    context.pump_ready_event = threading.Event()

    if adjust_pump_speed and context.spray_on and context.motor_service is not None:
        motor_address = context.get_motor_address_for_current_path()
        if motor_address == -1:
            _logger.warning("Invalid motor address — skipping dynamic pump adjustment")
        else:
            threshold = float(
                context.current_settings.get(GlueSettingKey.REACH_END_THRESHOLD.value, 1.0)
                if context.current_settings else 1.0
            )
            try:
                context.pump_thread = start_pump_speed_adjustment_thread(
                    motor_service=context.motor_service,
                    robot_service=context.robot_service,
                    settings=context.current_settings or {},
                    motor_address=motor_address,
                    path=context.current_path,
                    reach_end_threshold=threshold,
                    pump_ready_event=context.pump_ready_event,
                    start_point_index=context.current_point_index,
                    context=context,
                )
                if not context.pump_ready_event.wait(timeout=5.0):
                    _logger.error("Pump adjustment thread failed to become ready within 5 s")
                    return S.ERROR
                _logger.debug("Pump adjustment thread ready")
            except Exception:
                _logger.exception("Failed to start pump adjustment thread")
                return S.ERROR

    return S.SENDING_PATH_POINTS


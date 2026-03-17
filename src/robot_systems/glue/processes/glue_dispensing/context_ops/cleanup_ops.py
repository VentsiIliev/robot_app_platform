from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


class DispensingCleanupOps:
    def __init__(self, context) -> None:
        self._context = context

    def stop_robot_motion_safely(self) -> None:
        robot_service = self._context.robot_service
        if robot_service is None:
            return
        try:
            robot_service.stop_motion()
        except Exception:
            _logger.exception("stop_motion failed during cleanup")

    def stop_generator_if_running(self) -> None:
        context = self._context
        if not context.generator_started or context.generator is None:
            return
        try:
            context.generator.turn_off()
        except Exception:
            _logger.exception("generator turn_off failed during cleanup")
        context.mark_generator_stopped()

    def stop_pump_if_running(self) -> None:
        context = self._context
        if not context.motor_started or not context.spray_on or context.pump_controller is None:
            return
        motor_address = context.get_motor_address_for_current_path()
        if motor_address != -1:
            try:
                context.pump_controller.pump_off(motor_address, context.current_settings)
            except Exception:
                _logger.exception("pump_off failed during cleanup")
        context.mark_motor_stopped()

    def shutdown_best_effort(self, include_motion: bool = True) -> None:
        if include_motion:
            self.stop_robot_motion_safely()
        self.stop_pump_if_running()
        self.stop_generator_if_running()

import logging

from src.engine.robot.calibration.robot_calibration.states.fallback_targets import (
    get_target_marker_ids,
)
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import (
    RobotCalibrationStates,
)


_logger = logging.getLogger(__name__)


def set_calibration_error(context, message: str, *, log_level: str = "error") -> str:
    context.calibration_error_message = message
    log_method = getattr(_logger, log_level, _logger.error)
    log_method("Calibration error: %s", message)
    return message


def fail_calibration(
    context,
    message: str,
    *,
    log_level: str = "error",
) -> RobotCalibrationStates:
    set_calibration_error(context, message, log_level=log_level)
    return RobotCalibrationStates.ERROR


def build_error_notification(context) -> dict:
    target_ids = get_target_marker_ids(context)
    progress = context.progress
    artifacts = context.artifacts
    return {
        "status": "error",
        "message": context.calibration_error_message or "An unknown error occurred during calibration",
        "details": {
            "current_marker": progress.current_marker_id,
            "total_markers": len(target_ids),
            "successful_markers": len(artifacts.robot_positions_for_calibration),
            "iteration_count": progress.iteration_count,
            "max_iterations": progress.max_iterations,
        },
    }
